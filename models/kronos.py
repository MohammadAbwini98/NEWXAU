from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from _baseline_common import predict_with_profile


_PREDICTOR: Any | None = None
_LOAD_ERROR: str | None = None


def predict_proba(feature_vector: list[float]) -> tuple[float, float, float]:
    return _baseline_predict(feature_vector)


def predict_proba_market(feature_vector: list[float], context: dict[str, Any]) -> tuple[float, float, float]:
    if not _env_flag("KRONOS_USE_REAL_MODEL", True):
        return _baseline_predict(feature_vector)

    candles = context.get("candles") or []
    if len(candles) < 16:
        return _baseline_predict(feature_vector)

    try:
        prediction = _forecast_from_upstream(candles, context)
    except Exception as exc:
        global _LOAD_ERROR
        _LOAD_ERROR = str(exc)
        return _baseline_predict(feature_vector)

    last_close = float(candles[-1].get("close") or 0.0)
    forecast_close = float(prediction["close"].iloc[-1])
    if last_close <= 0:
        return _baseline_predict(feature_vector)

    edge = (forecast_close - last_close) / last_close
    return _edge_to_probs(edge)


def kronos_status() -> dict[str, Any]:
    return {
        "real_model_enabled": _env_flag("KRONOS_USE_REAL_MODEL", True),
        "loaded": _PREDICTOR is not None,
        "last_error": _LOAD_ERROR,
        "model_id": os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-mini"),
        "tokenizer_id": os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-2k"),
    }


def _baseline_predict(feature_vector: list[float]) -> tuple[float, float, float]:
    return predict_with_profile(feature_vector, tilt=0.05, sensitivity=1.10, hold_bias=0.01)


def _forecast_from_upstream(candles: list[dict[str, Any]], context: dict[str, Any]) -> Any:
    pd = _import_pandas()
    predictor = _load_predictor()

    frame = pd.DataFrame(candles).copy()
    frame["candle_time"] = pd.to_datetime(frame["candle_time"], utc=True)
    frame = frame.sort_values("candle_time").tail(int(os.getenv("KRONOS_LOOKBACK", "256")))
    for col in ("open", "high", "low", "close"):
        frame[col] = frame[col].astype(float)
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    frame["volume"] = frame["volume"].fillna(0.0).astype(float)
    frame["amount"] = frame["volume"] * frame[["open", "high", "low", "close"]].mean(axis=1)

    pred_len = int(os.getenv("KRONOS_PRED_LEN", str(context.get("prediction_horizon_candles") or 6)))
    pred_len = max(1, min(pred_len, 32))
    delta = _timeframe_delta(str(context.get("timeframe") or "1m"))
    last_ts = frame["candle_time"].iloc[-1]
    y_timestamp = pd.Series([last_ts + delta * (i + 1) for i in range(pred_len)])

    return predictor.predict(
        df=frame[["open", "high", "low", "close", "volume", "amount"]],
        x_timestamp=frame["candle_time"],
        y_timestamp=y_timestamp,
        pred_len=pred_len,
        T=float(os.getenv("KRONOS_TEMPERATURE", "1.0")),
        top_p=float(os.getenv("KRONOS_TOP_P", "0.9")),
        sample_count=int(os.getenv("KRONOS_SAMPLE_COUNT", "1")),
        verbose=False,
    )


def _load_predictor() -> Any:
    global _PREDICTOR, _LOAD_ERROR
    if _PREDICTOR is not None:
        return _PREDICTOR

    root = Path(__file__).resolve().parents[1]
    vendor_root = root / "vendor" / "Kronos"
    if not vendor_root.exists():
        raise FileNotFoundError(f"Upstream Kronos repo is missing: {vendor_root}")
    vendor_text = str(vendor_root)
    if vendor_text not in sys.path:
        sys.path.insert(0, vendor_text)

    import torch
    from model import Kronos, KronosPredictor, KronosTokenizer

    tokenizer_id = os.getenv("KRONOS_TOKENIZER_ID", "NeoQuasar/Kronos-Tokenizer-2k")
    model_id = os.getenv("KRONOS_MODEL_ID", "NeoQuasar/Kronos-mini")
    device = os.getenv("KRONOS_DEVICE") or ("cuda:0" if torch.cuda.is_available() else "cpu")
    max_context = int(os.getenv("KRONOS_MAX_CONTEXT", "512"))

    tokenizer = KronosTokenizer.from_pretrained(tokenizer_id)
    model = Kronos.from_pretrained(model_id)
    model.eval()
    _PREDICTOR = KronosPredictor(model, tokenizer, device=device, max_context=max_context)
    _LOAD_ERROR = None
    return _PREDICTOR


def _edge_to_probs(edge: float) -> tuple[float, float, float]:
    threshold = float(os.getenv("KRONOS_SIGNAL_EDGE_THRESHOLD", "0.001"))
    strength = min(abs(edge) / max(threshold, 1e-9), 3.0) / 3.0
    directional = 0.18 + 0.55 * strength
    hold = max(0.12, 0.58 - 0.36 * strength)
    opposite = max(0.08, 1.0 - directional - hold)
    if edge > 0:
        buy, sell = directional, opposite
    else:
        buy, sell = opposite, directional
    total = buy + sell + hold
    return buy / total, sell / total, hold / total


def _timeframe_delta(timeframe: str) -> timedelta:
    return {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
    }.get(timeframe, timedelta(minutes=1))


def _import_pandas() -> Any:
    import pandas as pd

    return pd


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
