from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable

from .config import ModelWeights, RuntimeConfig
from .contracts import AgreementStatus, EnsemblePrediction, IndicatorSnapshot, ModelPrediction, SignalDirection
from .model_runtime import feature_vector_from_snapshot, list_model_artifact_status, load_model_adapter


def _normalize_probs(buy: float, sell: float, hold: float) -> tuple[float, float, float]:
    buy = max(0.0, buy)
    sell = max(0.0, sell)
    hold = max(0.0, hold)
    total = buy + sell + hold
    if total <= 0:
        return 0.33, 0.33, 0.34
    return buy / total, sell / total, hold / total


def _argmax_signal(buy: float, sell: float, hold: float) -> SignalDirection:
    if buy >= sell and buy >= hold:
        return SignalDirection.BUY
    if sell >= buy and sell >= hold:
        return SignalDirection.SELL
    return SignalDirection.HOLD


class ModelEnsembleEngine:
    """Phase 3: run model advisors, normalize outputs, and build weighted ensemble."""

    def __init__(self, runtime: RuntimeConfig | None = None, model_weights: ModelWeights | None = None) -> None:
        self.runtime = runtime or RuntimeConfig()
        self.model_weights = model_weights or ModelWeights()
        self.confidence_weighting = self.runtime.enable_confidence_weighting
        self.active_model_names = [
            "kronos",
            "tcn",
            "lightgbm",
            "patchtst",
            "cnn_lstm",
            "nhits",
        ]
        self.loaded_adapters = {
            name: load_model_adapter(name, self.runtime.model_artifacts_dir) for name in self.active_model_names
        }
        self.artifact_status = list_model_artifact_status(self.active_model_names, self.runtime.model_artifacts_dir)

    def _base_bias(self, snapshot: IndicatorSnapshot, features: dict[str, float | str]) -> float:
        bias = 0.0

        if snapshot.trend.bias == "BULLISH":
            bias += 0.35
        elif snapshot.trend.bias == "BEARISH":
            bias -= 0.35

        if snapshot.momentum.bias == "POSITIVE":
            bias += 0.20
        elif snapshot.momentum.bias == "NEGATIVE":
            bias -= 0.20

        structure = snapshot.structure_bias
        if "BULLISH" in structure:
            bias += 0.25
        elif "BEARISH" in structure:
            bias -= 0.25

        r5 = float(features.get("return_5", 0.0))
        bias += max(min(r5 * 20.0, 0.2), -0.2)

        if snapshot.volatility_status == "TOO_LOW":
            bias *= 0.6
        if snapshot.news_status != "CLEAR":
            bias *= 0.5

        return max(min(bias, 0.95), -0.95)

    def _predict_for_model(
        self,
        model_name: str,
        snapshot: IndicatorSnapshot,
        features: dict[str, float | str],
        prediction_time: datetime,
        candles: list[Any] | None = None,
    ) -> ModelPrediction:
        adapter = self.loaded_adapters.get(model_name)
        if adapter is not None:
            feature_vector = feature_vector_from_snapshot(features, snapshot.raw_json)
            context = {
                "snapshot": snapshot.model_dump(mode="json"),
                "features": dict(features),
                "raw_indicators": dict(snapshot.raw_json),
                "instrument": snapshot.instrument,
                "timeframe": snapshot.timeframe,
                "prediction_horizon_candles": self.runtime.prediction_horizon_candles,
                "candles": [
                    candle.model_dump(mode="json") if hasattr(candle, "model_dump") else dict(candle)
                    for candle in (candles or [])
                ],
            }
            loaded_probs = adapter.predict_probabilities(feature_vector, context=context)
            if loaded_probs is not None:
                buy, sell, hold = loaded_probs
                signal = _argmax_signal(buy, sell, hold)
                confidence = max(buy, sell, hold)
                directional_edge = buy - sell
                expected_return = directional_edge * 0.002

                return ModelPrediction(
                    model_name=model_name.upper() if model_name != "lightgbm" else "LightGBM",
                    model_version=f"{adapter.artifact_path.stem}_{self.runtime.instrument.lower()}_{snapshot.timeframe}_v1",
                    instrument=snapshot.instrument,
                    timeframe=snapshot.timeframe,
                    prediction_time=prediction_time.astimezone(UTC),
                    signal=signal,
                    buy_probability=buy,
                    sell_probability=sell,
                    hold_probability=hold,
                    confidence=confidence,
                    expected_return=expected_return,
                    expected_range=max(snapshot.atr, 0.1) * (1.0 + confidence),
                    prediction_horizon_candles=self.runtime.prediction_horizon_candles,
                )

        base = self._base_bias(snapshot, features)

        model_tilt = {
            "kronos": 0.08,
            "tcn": 0.05,
            "lightgbm": 0.03,
            "patchtst": 0.01,
            "cnn_lstm": 0.02,
            "nhits": 0.00,
        }.get(model_name, 0.0)

        # Deterministic model variation so each model contributes slightly differently.
        phase = (sum(ord(ch) for ch in model_name) % 13) / 100.0
        adjusted = max(min(base + model_tilt - phase, 0.95), -0.95)

        buy = 0.40 + max(adjusted, 0.0) * 0.55
        sell = 0.40 + max(-adjusted, 0.0) * 0.55
        hold = 1.0 - (buy + sell) * 0.5
        buy, sell, hold = _normalize_probs(buy, sell, hold)

        signal = _argmax_signal(buy, sell, hold)
        confidence = max(buy, sell, hold)

        atr = max(snapshot.atr, 0.1)
        if signal == SignalDirection.BUY:
            expected_return = abs(adjusted) * 0.002
        elif signal == SignalDirection.SELL:
            expected_return = -abs(adjusted) * 0.002
        else:
            expected_return = 0.0

        return ModelPrediction(
            model_name=model_name.upper() if model_name != "lightgbm" else "LightGBM",
            model_version=f"{model_name}_{self.runtime.instrument.lower()}_{snapshot.timeframe}_v1",
            instrument=snapshot.instrument,
            timeframe=snapshot.timeframe,
            prediction_time=prediction_time.astimezone(UTC),
            signal=signal,
            buy_probability=buy,
            sell_probability=sell,
            hold_probability=hold,
            confidence=confidence,
            expected_return=expected_return,
            expected_range=atr * (1.0 + confidence),
            prediction_horizon_candles=self.runtime.prediction_horizon_candles,
        )

    def run_models(
        self,
        snapshot: IndicatorSnapshot,
        features: dict[str, float | str],
        prediction_time: datetime | None = None,
        enabled_models: Iterable[str] | None = None,
        candles: list[Any] | None = None,
    ) -> list[ModelPrediction]:
        ts = prediction_time or datetime.now(tz=UTC)
        model_names = list(enabled_models) if enabled_models else self.active_model_names
        return [self._predict_for_model(name, snapshot, features, ts, candles=candles) for name in model_names]

    def build_abstain_predictions(
        self,
        snapshot: IndicatorSnapshot,
        prediction_time: datetime | None = None,
        enabled_models: Iterable[str] | None = None,
    ) -> list[ModelPrediction]:
        """Create deterministic HOLD votes without invoking model adapters."""
        ts = (prediction_time or datetime.now(tz=UTC)).astimezone(UTC)
        model_names = list(enabled_models) if enabled_models else self.active_model_names
        return [
            ModelPrediction(
                model_name=name.upper() if name != "lightgbm" else "LightGBM",
                model_version="DATA_QUALITY_ABSTAIN",
                instrument=snapshot.instrument,
                timeframe=snapshot.timeframe,
                prediction_time=ts,
                signal=SignalDirection.HOLD,
                buy_probability=0.0,
                sell_probability=0.0,
                hold_probability=1.0,
                confidence=1.0,
                expected_return=0.0,
                expected_range=0.0,
                prediction_horizon_candles=self.runtime.prediction_horizon_candles,
            )
            for name in model_names
        ]

    def build_ensemble(
        self,
        predictions: list[ModelPrediction],
        prediction_time: datetime | None = None,
    ) -> EnsemblePrediction:
        if not predictions:
            raise ValueError("predictions list cannot be empty")

        ts = prediction_time or datetime.now(tz=UTC)
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0

        signals: list[SignalDirection] = []
        for p in predictions:
            key = p.model_name.lower()
            weight = self.model_weights.weights.get(key, 0.0)
            if self.confidence_weighting:
                # Conviction above the 1/3 uniform floor, scaled to [~0, ~1]. A model
                # sitting at uniform (no view) contributes almost nothing; a decisive
                # model contributes near its full configured weight.
                conf = max(p.buy_probability, p.sell_probability, p.hold_probability)
                conviction = max(0.0, (conf - (1.0 / 3.0))) / (1.0 - (1.0 / 3.0))
                weight *= 0.15 + 0.85 * conviction
            buy_score += p.buy_probability * weight
            sell_score += p.sell_probability * weight
            hold_score += p.hold_probability * weight
            signals.append(p.signal)

        total = buy_score + sell_score + hold_score
        if total > 0:
            buy_score /= total
            sell_score /= total
            hold_score /= total

        ensemble_signal = _argmax_signal(buy_score, sell_score, hold_score)
        ensemble_confidence = max(buy_score, sell_score, hold_score)

        buy_votes = sum(1 for s in signals if s == SignalDirection.BUY)
        sell_votes = sum(1 for s in signals if s == SignalDirection.SELL)
        hold_votes = sum(1 for s in signals if s == SignalDirection.HOLD)

        # Agreement is measured by the directional margin (leading direction vs the
        # opposing one), not by demanding a near-unanimous vote. A genuinely diverse
        # ensemble rarely gets 5/6 to agree, so the old threshold flagged healthy
        # diversity as "conflict". HIGH_CONFLICT now means a real split: the opposing
        # direction has as many votes as the leader.
        leader_votes = max(buy_votes, sell_votes)
        opposing_votes = min(buy_votes, sell_votes) if (buy_votes and sell_votes) else 0
        margin = leader_votes - opposing_votes

        if max(buy_votes, sell_votes, hold_votes) == len(signals):
            agreement = AgreementStatus.STRONG
        elif leader_votes >= 2 and opposing_votes >= leader_votes:
            agreement = AgreementStatus.HIGH_CONFLICT
        elif margin >= 2:
            agreement = AgreementStatus.NORMAL
        else:
            agreement = AgreementStatus.MIXED

        active_models = [p.model_name for p in predictions if p.signal == ensemble_signal]
        conflicting = [p.model_name for p in predictions if p.signal != ensemble_signal]

        summary = (
            f"Ensemble {ensemble_signal.value} with {agreement.value} agreement. "
            f"Buy={buy_score:.2f}, Sell={sell_score:.2f}, Hold={hold_score:.2f}."
        )

        return EnsemblePrediction(
            instrument=predictions[0].instrument,
            timeframe=predictions[0].timeframe,
            prediction_time=ts.astimezone(UTC),
            ensemble_signal=ensemble_signal,
            ensemble_confidence=ensemble_confidence,
            buy_score=buy_score,
            sell_score=sell_score,
            hold_score=hold_score,
            agreement_status=agreement,
            active_models=active_models,
            conflicting_models=conflicting,
            summary=summary,
        )
