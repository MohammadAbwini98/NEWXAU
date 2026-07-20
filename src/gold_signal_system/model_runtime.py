from __future__ import annotations

import contextlib
import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .contracts import SignalDirection


MODEL_ARTIFACT_SUFFIXES = (".joblib", ".pkl", ".pt", ".pth", ".onnx", ".py")


def _softmax(values: list[float]) -> list[float]:
    if not values:
        return [0.33, 0.33, 0.34]
    max_value = max(values)
    exps = [math.exp(v - max_value) for v in values]
    total = sum(exps)
    if total <= 0:
        return [0.33, 0.33, 0.34]
    return [v / total for v in exps]


@dataclass(slots=True)
class LoadedModelAdapter:
    model_name: str
    artifact_path: Path
    kind: str
    runtime: Any

    def predict_probabilities(
        self,
        feature_vector: list[float],
        context: dict[str, Any] | None = None,
    ) -> tuple[float, float, float] | None:
        if self.kind == "joblib":
            return _predict_joblib(self.runtime, feature_vector)
        if self.kind == "torch":
            return _predict_torch(self.runtime, feature_vector)
        if self.kind == "onnx":
            return _predict_onnx(self.runtime, feature_vector)
        if self.kind == "python":
            return _predict_python(self.runtime, feature_vector, context=context)
        return None


def _normalize_three(values: list[float]) -> tuple[float, float, float] | None:
    if not values:
        return None
    if len(values) == 2:
        # Assume binary [SELL, BUY] and derive HOLD from uncertainty.
        sell, buy = float(values[0]), float(values[1])
        hold = max(0.0, 1.0 - max(buy, sell))
        total = buy + sell + hold
        if total <= 0:
            return None
        return buy / total, sell / total, hold / total

    if len(values) >= 3:
        buy, sell, hold = float(values[0]), float(values[1]), float(values[2])
        total = buy + sell + hold
        if total <= 0:
            return None
        return buy / total, sell / total, hold / total

    return None


def _predict_joblib(model: Any, feature_vector: list[float]) -> tuple[float, float, float] | None:
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba([feature_vector])[0]
        normalized = _normalize_three(list(map(float, probs)))
        if normalized:
            return normalized

    if hasattr(model, "predict"):
        pred = model.predict([feature_vector])[0]
        if isinstance(pred, str):
            return _label_to_probs(pred)
        if isinstance(pred, (int, float)):
            idx = int(pred)
            mapping = {
                0: (0.15, 0.70, 0.15),  # SELL class index
                1: (0.70, 0.15, 0.15),  # BUY class index
                2: (0.15, 0.15, 0.70),  # HOLD class index
            }
            return mapping.get(idx, (0.33, 0.33, 0.34))

    return None


def _predict_torch(model: Any, feature_vector: list[float]) -> tuple[float, float, float] | None:
    import torch

    with torch.no_grad():
        x = torch.tensor([feature_vector], dtype=torch.float32)
        output = model(x)
        if hasattr(output, "detach"):
            raw = output.detach().cpu().tolist()
            if raw and isinstance(raw[0], list):
                probs = _softmax([float(v) for v in raw[0]])
                normalized = _normalize_three(probs)
                if normalized:
                    return normalized
    return None


def _predict_onnx(session: Any, feature_vector: list[float]) -> tuple[float, float, float] | None:
    import numpy as np

    inputs = session.get_inputs()
    if not inputs:
        return None
    input_name = inputs[0].name

    outputs = session.run(None, {input_name: np.array([feature_vector], dtype=np.float32)})
    if not outputs:
        return None

    first = outputs[0]
    if hasattr(first, "tolist"):
        values = first.tolist()
        if values and isinstance(values[0], list):
            probs = _softmax([float(v) for v in values[0]])
            normalized = _normalize_three(probs)
            if normalized:
                return normalized
    return None


def _predict_python(
    module: ModuleType,
    feature_vector: list[float],
    context: dict[str, Any] | None = None,
) -> tuple[float, float, float] | None:
    if context is not None and hasattr(module, "predict_proba_market"):
        try:
            values = module.predict_proba_market(feature_vector, context)
            normalized = _normalize_three(list(values))
            if normalized:
                return normalized
        except Exception:
            return None

    if hasattr(module, "predict_proba"):
        try:
            values = module.predict_proba(feature_vector)
            normalized = _normalize_three(list(values))
            if normalized:
                return normalized
        except Exception:
            return None

    if hasattr(module, "predict"):
        try:
            pred = module.predict(feature_vector)
            if isinstance(pred, str):
                return _label_to_probs(pred)
        except Exception:
            return None
    return None


def _label_to_probs(label: str) -> tuple[float, float, float]:
    text = (label or "").strip().upper()
    if text == SignalDirection.BUY.value:
        return 0.7, 0.15, 0.15
    if text == SignalDirection.SELL.value:
        return 0.15, 0.7, 0.15
    return 0.15, 0.15, 0.7


def load_model_adapter(model_name: str, artifact_dir: str) -> LoadedModelAdapter | None:
    artifact = find_model_artifact(model_name, artifact_dir)
    if artifact is None:
        return None

    suffix = artifact.suffix.lower()

    if suffix in (".joblib", ".pkl"):
        try:
            import joblib

            return LoadedModelAdapter(model_name=model_name, artifact_path=artifact, kind="joblib", runtime=joblib.load(artifact))
        except Exception:
            return None

    if suffix in (".pt", ".pth"):
        try:
            import torch

            runtime = torch.jit.load(str(artifact))
            runtime.eval()
            return LoadedModelAdapter(model_name=model_name, artifact_path=artifact, kind="torch", runtime=runtime)
        except Exception:
            return None

    if suffix == ".onnx":
        try:
            import onnxruntime as ort

            session = ort.InferenceSession(str(artifact), providers=["CPUExecutionProvider"])
            return LoadedModelAdapter(model_name=model_name, artifact_path=artifact, kind="onnx", runtime=session)
        except Exception:
            return None

    if suffix == ".py":
        try:
            module_name = f"runtime_model_{model_name}"
            spec = importlib.util.spec_from_file_location(module_name, artifact)
            if spec is None or spec.loader is None:
                return None
            module = importlib.util.module_from_spec(spec)
            artifact_parent = str(artifact.parent.resolve())
            inserted = False
            if artifact_parent not in sys.path:
                sys.path.insert(0, artifact_parent)
                inserted = True
            try:
                spec.loader.exec_module(module)
            finally:
                if inserted:
                    with contextlib.suppress(ValueError):
                        sys.path.remove(artifact_parent)
            return LoadedModelAdapter(model_name=model_name, artifact_path=artifact, kind="python", runtime=module)
        except Exception:
            return None

    return None


def find_model_artifact(model_name: str, artifact_dir: str) -> Path | None:
    base = Path(artifact_dir)
    if not base.exists():
        return None

    candidates = [base / f"{model_name}{suffix}" for suffix in MODEL_ARTIFACT_SUFFIXES]
    return next((p for p in candidates if p.exists()), None)


def list_model_artifact_status(model_names: list[str], artifact_dir: str) -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for name in model_names:
        artifact = find_model_artifact(name, artifact_dir)
        if artifact is None:
            status[name] = {
                "status": "MISSING",
                "path": None,
                "kind": None,
            }
            continue

        adapter = load_model_adapter(name, artifact_dir)
        status[name] = {
            "status": "LOADED" if adapter is not None else "LOAD_FAILED",
            "path": str(artifact),
            "kind": adapter.kind if adapter is not None else artifact.suffix.lower().lstrip("."),
        }
    return status


def feature_vector_from_snapshot(features: dict[str, float | str], raw_indicators: dict[str, Any]) -> list[float]:
    keys = [
        "return_1",
        "return_5",
        "return_20",
        "rolling_mean_20",
        "rolling_std_20",
        "atr_14",
        "realized_volatility",
        "distance_to_ema20",
        "distance_to_ema50",
    ]

    vector = [float(features.get(k, 0.0) or 0.0) for k in keys]
    vector.extend(
        [
            float(raw_indicators.get("ema20", 0.0) or 0.0),
            float(raw_indicators.get("ema50", 0.0) or 0.0),
            float(raw_indicators.get("ema100", 0.0) or 0.0),
            float(raw_indicators.get("ema200", 0.0) or 0.0),
            float(raw_indicators.get("rsi14", 50.0) or 50.0),
            float(raw_indicators.get("macd_hist", 0.0) or 0.0),
            float(raw_indicators.get("atr14", 0.0) or 0.0),
            float(raw_indicators.get("atr_pct", 0.0) or 0.0),
        ]
    )

    return vector
