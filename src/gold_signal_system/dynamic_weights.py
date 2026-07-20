from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .contracts import ModelPrediction
from .market_sessions import normalize_gold_session_name


@dataclass(slots=True)
class ModelWeightResult:
    model_name: str
    base_weight: float
    effective_weight: float
    adjustment_reason: dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def model_dump(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "base_weight": round(self.base_weight, 8),
            "effective_weight": round(self.effective_weight, 8),
            "adjustment_reason": self.adjustment_reason,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass(slots=True)
class ModelWeightProfile:
    model_name: str
    base_weight: float
    min_weight: float = 0.01
    max_weight: float = 0.60
    is_enabled: bool = True
    applies_to_timeframe: str = "*"


class DynamicModelWeightService:
    def __init__(
        self,
        min_weight: float = 0.01,
        max_weight: float = 0.60,
        max_change_per_update: float = 0.03,
        performance_window: int = 100,
        min_observations_for_reweight: int = 10,
    ) -> None:
        self.profiles: dict[str, ModelWeightProfile] = {}
        self.history: list[ModelWeightResult] = []
        self.profile_versions: list[dict[str, Any]] = []
        self.active_profile_version = 1
        self.default_min_weight = min_weight
        self.default_max_weight = max_weight
        self.max_change_per_update = max_change_per_update
        self.performance_window = performance_window
        self.min_observations_for_reweight = min_observations_for_reweight
        self._last_effective_weights: dict[str, float] = {}

    def calculate(
        self,
        base_weights: dict[str, float],
        predictions: list[ModelPrediction],
        metrics: dict[str, dict[str, Any]],
        market_regime: str = "UNKNOWN",
        session: str = "UNKNOWN",
        health_by_model: dict[str, str] | None = None,
    ) -> list[ModelWeightResult]:
        health_by_model = health_by_model or {}
        raw: dict[str, tuple[float, dict[str, Any], ModelWeightProfile]] = {}

        for prediction in predictions:
            name = prediction.model_name.lower()
            base = float(base_weights.get(name, 0.0))
            profile = self.profiles.get(name) or ModelWeightProfile(
                model_name=name,
                base_weight=base,
                min_weight=self.default_min_weight,
                max_weight=self.default_max_weight,
            )
            if not profile.is_enabled:
                raw[name] = (0.0, {"health_factor": 0.0, "reason": "Model disabled"}, profile)
                continue
            if health_by_model.get(name) == "FAILED":
                raw[name] = (0.0, {"health_factor": 0.0, "reason": "Model health failed"}, profile)
                continue

            metric = metrics.get(name, {})
            factors = self._factors(prediction, metric, market_regime, session)
            value = base
            for key, factor in factors.items():
                if not key.endswith("_factor"):
                    continue
                if isinstance(factor, (int, float)):
                    value *= float(factor)
            value = max(profile.min_weight, min(profile.max_weight, value))
            previous = self._last_effective_weights.get(name)
            if previous is not None and not factors.get("baseline_retained"):
                value = max(previous - self.max_change_per_update, min(previous + self.max_change_per_update, value))
            raw[name] = (value, factors, profile)

        total = sum(item[0] for item in raw.values())
        if total <= 0:
            if raw:
                results = [
                    ModelWeightResult(
                        model_name=name,
                        base_weight=float(base_weights.get(name, profile.base_weight)),
                        effective_weight=0.0,
                        adjustment_reason=reason,
                    )
                    for name, (_value, reason, profile) in raw.items()
                ]
                self.history.extend(results)
                return results
            total = sum(float(base_weights.get(p.model_name.lower(), 0.0)) for p in predictions) or 1.0
            raw = {
                p.model_name.lower(): (
                    float(base_weights.get(p.model_name.lower(), 0.0)),
                    {"reason": "Fallback to base weights"},
                    self.profiles.get(p.model_name.lower()) or ModelWeightProfile(p.model_name.lower(), float(base_weights.get(p.model_name.lower(), 0.0))),
                )
                for p in predictions
            }

        results: list[ModelWeightResult] = []
        for name, (value, reason, profile) in raw.items():
            base = float(base_weights.get(name, profile.base_weight))
            results.append(
                ModelWeightResult(
                    model_name=name,
                    base_weight=base,
                    effective_weight=value / total,
                    adjustment_reason=reason,
                )
            )

        self.history.extend(results)
        self._last_effective_weights = {item.model_name: item.effective_weight for item in results}
        self._save_profile_version(results, market_regime, session)
        return results

    def set_profile(self, model_name: str, profile: ModelWeightProfile) -> None:
        self.profiles[model_name.lower()] = profile

    def current_weights(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, ModelWeightResult] = {}
        for item in self.history:
            latest[item.model_name] = item
        return {name: item.model_dump() for name, item in latest.items()}

    def rollback(self, version: int) -> dict[str, Any]:
        profile = next((item for item in self.profile_versions if item["version"] == version), None)
        if profile is None:
            return {"status": "NOT_FOUND", "version": version}
        self.active_profile_version = version
        self._last_effective_weights = dict(profile["weights"])
        return {"status": "OK", "active_profile": profile}

    def _save_profile_version(self, results: list[ModelWeightResult], market_regime: str, session: str) -> None:
        weights = {item.model_name: item.effective_weight for item in results}
        if self.profile_versions and self.profile_versions[-1]["weights"] == weights:
            return
        self.active_profile_version = len(self.profile_versions) + 1
        self.profile_versions.append(
            {
                "profile_id": self.active_profile_version,
                "version": self.active_profile_version,
                "is_active": True,
                "created_at": datetime.now(tz=UTC).isoformat(),
                "model_weights_json": weights,
                "weights": weights,
                "reason_summary": "Dynamic weights recalculated from validated performance and context.",
                "performance_window": self.performance_window,
                "min_weight": self.default_min_weight,
                "max_weight": self.default_max_weight,
                "max_change_per_update": self.max_change_per_update,
                "market_regime": market_regime,
                "session": session,
            }
        )

    def _factors(self, prediction: ModelPrediction, metric: dict[str, Any], market_regime: str, session: str) -> dict[str, Any]:
        observations = int(metric.get("observations", 0) or metric.get("number_of_predictions", 0) or 0)
        if observations < self.min_observations_for_reweight:
            reason = (
                f"Insufficient performance data ({observations}/{self.min_observations_for_reweight}); "
                "configured baseline retained."
            )
            return {
                "recent_performance_factor": 1.0,
                "direction_factor": 1.0,
                "session_factor": 1.0,
                "regime_factor": 1.0,
                "confidence_calibration_factor": 1.0,
                "health_factor": 1.0,
                "observations": observations,
                "required_observations": self.min_observations_for_reweight,
                "baseline_retained": True,
                "reason": reason,
            }
        else:
            win_rate = float(metric.get("win_rate", metric.get("model_win_rate", 0.0)) or 0.0)
            if win_rate >= 0.60:
                performance_factor = 1.15
            elif win_rate >= 0.50:
                performance_factor = 1.00
            elif win_rate >= 0.45:
                performance_factor = 0.85
            else:
                performance_factor = 0.65
            reason = f"Recent win rate {win_rate:.2f}."

        signal = prediction.signal.value
        precision_key = "buy_precision" if signal == "BUY" else "sell_precision" if signal == "SELL" else "hold_accuracy"
        precision = float(metric.get(precision_key, 0.0) or 0.0)
        direction_factor = 1.10 if precision >= 0.60 else 0.85 if observations >= 3 and precision < 0.45 else 1.0
        regime_factor = self._regime_factor(prediction.model_name.lower(), market_regime)
        normalized_session = normalize_gold_session_name(session)
        session_factor = (
            1.05
            if normalized_session in {"LONDON_ACTIVE", "NY_ACTIVE"} and prediction.model_name.lower() in {"lightgbm", "kronos"}
            else 1.0
        )
        calibration_factor = 1.05 if prediction.confidence >= 0.70 and precision >= 0.55 else 0.95 if prediction.confidence >= 0.80 and precision < 0.45 and observations >= 3 else 1.0

        return {
            "recent_performance_factor": performance_factor,
            "direction_factor": direction_factor,
            "session_factor": session_factor,
            "regime_factor": regime_factor,
            "confidence_calibration_factor": calibration_factor,
            "health_factor": 1.0,
            "reason": reason,
        }

    def _regime_factor(self, model_name: str, regime: str) -> float:
        if regime in {"TRENDING_UP", "TRENDING_DOWN"} and model_name in {"tcn", "patchtst"}:
            return 1.10
        if regime == "RANGING" and model_name == "lightgbm":
            return 1.10
        if regime in {"HIGH_VOLATILITY", "BREAKOUT"} and model_name == "nhits":
            return 1.08
        if regime == "CHOPPY":
            return 0.90
        return 1.0
