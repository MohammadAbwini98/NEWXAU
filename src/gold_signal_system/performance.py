from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .contracts import FinalRecommendation, SignalDirection


@dataclass(slots=True)
class ModelPerformanceState:
    buy_signals: int = 0
    sell_signals: int = 0
    hold_signals: int = 0
    buy_wins: int = 0
    sell_wins: int = 0
    hold_hits: int = 0
    agree_signals: int = 0
    agree_wins: int = 0
    false_signals: int = 0
    total_outcomes: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    sum_return: float = 0.0
    confidence_sum: float = 0.0
    confidence_count: int = 0
    confidence_buckets: dict[str, list[int]] | None = None


class ModelPerformanceTracker:
    """Tracks model quality and generates adaptive ensemble weights."""

    def __init__(self, min_observations_for_reweight: int = 10) -> None:
        self.states: dict[str, ModelPerformanceState] = {}
        self.min_observations_for_reweight = min_observations_for_reweight
        self.last_updated_at: datetime | None = None

    def _state(self, model_name: str) -> ModelPerformanceState:
        key = model_name.lower()
        if key not in self.states:
            self.states[key] = ModelPerformanceState(confidence_buckets={})
        return self.states[key]

    def record_outcome(
        self,
        recommendation: FinalRecommendation,
        realized_rr: float,
        outcome: str,
        source: str,
    ) -> None:
        success = realized_rr > 0.0
        final_signal = recommendation.signal

        for vote in recommendation.model_votes:
            state = self._state(vote.model_name)
            state.total_outcomes += 1
            state.confidence_sum += vote.confidence
            state.confidence_count += 1
            bucket = self._confidence_bucket(vote.confidence)
            if state.confidence_buckets is not None:
                wins_total = state.confidence_buckets.setdefault(bucket, [0, 0])
                wins_total[1] += 1
                if success:
                    wins_total[0] += 1

            if vote.signal == SignalDirection.BUY:
                state.buy_signals += 1
                if success and final_signal == SignalDirection.BUY:
                    state.buy_wins += 1
            elif vote.signal == SignalDirection.SELL:
                state.sell_signals += 1
                if success and final_signal == SignalDirection.SELL:
                    state.sell_wins += 1
            else:
                state.hold_signals += 1
                if final_signal == SignalDirection.HOLD:
                    state.hold_hits += 1

            if vote.signal == final_signal and final_signal != SignalDirection.HOLD:
                state.agree_signals += 1
                if success:
                    state.agree_wins += 1
                    state.gross_profit += realized_rr
                else:
                    state.gross_loss += abs(realized_rr)
                    state.false_signals += 1
                state.sum_return += realized_rr

        self.last_updated_at = datetime.now(tz=UTC)

    def metrics(self) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}

        for name, state in self.states.items():
            buy_precision = (state.buy_wins / state.buy_signals) if state.buy_signals else 0.0
            sell_precision = (state.sell_wins / state.sell_signals) if state.sell_signals else 0.0
            hold_accuracy = (state.hold_hits / state.hold_signals) if state.hold_signals else 0.0
            win_rate = (state.agree_wins / state.agree_signals) if state.agree_signals else 0.0
            profit_factor = (
                (state.gross_profit / state.gross_loss)
                if state.gross_loss > 0
                else (state.gross_profit if state.gross_profit > 0 else 0.0)
            )
            false_signal_rate = (state.false_signals / state.agree_signals) if state.agree_signals else 0.0
            average_return = (state.sum_return / state.agree_signals) if state.agree_signals else 0.0
            avg_confidence = (state.confidence_sum / state.confidence_count) if state.confidence_count else 0.0
            drift_score = max(0.0, min(1.0, 1.0 - avg_confidence))

            output[name] = {
                "model_win_rate": round(win_rate, 6),
                "buy_precision": round(buy_precision, 6),
                "sell_precision": round(sell_precision, 6),
                "hold_accuracy": round(hold_accuracy, 6),
                "win_rate": round(win_rate, 6),
                "average_confidence": round(avg_confidence, 6),
                "confidence_calibration": self._bucket_metrics(state.confidence_buckets or {}),
                "profit_factor": round(profit_factor, 6),
                "profit_factor_contribution": round(profit_factor, 6),
                "false_signal_rate": round(false_signal_rate, 6),
                "average_return": round(average_return, 8),
                "average_pnl_points": round(average_return, 8),
                "max_drawdown_contribution": 0.0,
                "drift_score": round(drift_score, 6),
                "observations": state.total_outcomes,
                "number_of_predictions": state.total_outcomes,
                "number_of_recommended_predictions": state.agree_signals,
                "source": "mixed",  # updated at persistence call site
            }

        return output

    def suggested_weights(self, base_weights: dict[str, float]) -> dict[str, float]:
        if not base_weights:
            return {}

        metrics = self.metrics()
        if not metrics:
            return dict(base_weights)

        weighted: dict[str, float] = {}
        for model_name, base in base_weights.items():
            metric = metrics.get(model_name)
            if not metric or metric.get("observations", 0) < self.min_observations_for_reweight:
                weighted[model_name] = float(base)
                continue

            precision = (float(metric["buy_precision"]) + float(metric["sell_precision"])) / 2.0
            win_rate = float(metric["win_rate"])
            profit_factor_norm = min(float(metric["profit_factor"]), 3.0) / 3.0
            false_signal_penalty = 1.0 - float(metric["false_signal_rate"])

            score = (
                0.35 * win_rate
                + 0.30 * precision
                + 0.20 * profit_factor_norm
                + 0.15 * false_signal_penalty
            )
            score += ((sum(ord(ch) for ch in model_name) % 5) - 2) * 0.01

            # Keep adaptation controlled around original weight.
            multiplier = 0.6 + score
            weighted[model_name] = max(float(base) * multiplier, 0.01)

        total = sum(weighted.values())
        if total <= 0:
            return dict(base_weights)

        normalized = {k: v / total for k, v in weighted.items()}
        return normalized

    def model_metrics(self, model_name: str) -> dict[str, Any]:
        return self.metrics().get(model_name.lower(), {})

    def confidence_calibration(self) -> dict[str, Any]:
        return {
            model_name: metrics.get("confidence_calibration", {})
            for model_name, metrics in self.metrics().items()
        }

    def by_regime(self) -> dict[str, Any]:
        return {
            "status": "AVAILABLE_AFTER_REGIME_TAGGED_OUTCOMES",
            "metrics": self.metrics(),
        }

    def _confidence_bucket(self, confidence: float) -> str:
        if confidence < 0.60:
            return "0.50-0.60"
        if confidence < 0.70:
            return "0.60-0.70"
        if confidence < 0.80:
            return "0.70-0.80"
        if confidence < 0.90:
            return "0.80-0.90"
        return "0.90-1.00"

    def _bucket_metrics(self, buckets: dict[str, list[int]]) -> dict[str, Any]:
        return {
            bucket: {
                "wins": values[0],
                "predictions": values[1],
                "actual_win_rate": round(values[0] / values[1], 6) if values[1] else 0.0,
            }
            for bucket, values in sorted(buckets.items())
        }
