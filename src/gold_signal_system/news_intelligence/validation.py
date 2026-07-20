from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .models import NewsDirection, NewsImpactValidationModel


HORIZON_THRESHOLDS = {
    5: 0.0004,
    15: 0.0006,
    30: 0.0010,
    60: 0.0015,
    240: 0.0030,
}


class NewsImpactValidator:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def evaluate_ready_analyses(self, instrument: str, candles: list[Any]) -> dict[str, Any]:
        if not candles:
            return {"evaluated": 0, "message": "No candles available for news validation."}
        analyses = self.repository.get_ai_analyses(instrument, limit=200)
        evaluated = 0
        for analysis in analyses:
            analysis_id = analysis.get("id")
            created_at = self._parse_dt(analysis.get("created_at"))
            if analysis_id is None or created_at is None:
                continue
            price_at_analysis = self._price_at_or_after(candles, created_at)
            if price_at_analysis is None:
                continue
            for horizon, threshold in HORIZON_THRESHOLDS.items():
                horizon_at = created_at + timedelta(minutes=horizon)
                price_at_horizon = self._price_at_or_after(candles, horizon_at)
                if price_at_horizon is None:
                    continue
                return_pct = (price_at_horizon - price_at_analysis) / price_at_analysis
                actual = self._actual_direction(return_pct, threshold)
                predicted = str(analysis.get("direction") or NewsDirection.UNKNOWN.value)
                was_correct = self._is_correct(predicted, actual)
                validation = NewsImpactValidationModel(
                    analysis_id=int(analysis_id),
                    instrument=instrument,
                    horizon_minutes=horizon,
                    predicted_direction=predicted,
                    actual_direction=actual,
                    price_at_analysis=price_at_analysis,
                    price_at_horizon=price_at_horizon,
                    return_pct=round(return_pct * 100.0, 6),
                    was_correct=was_correct,
                    notes="forward_shadow_validation",
                )
                if self.repository.save_validation(validation):
                    evaluated += 1
        return {"evaluated": evaluated}

    @staticmethod
    def _actual_direction(return_pct: float, threshold: float) -> str:
        if return_pct > threshold:
            return NewsDirection.UP.value
        if return_pct < -threshold:
            return NewsDirection.DOWN.value
        return NewsDirection.NEUTRAL.value

    @staticmethod
    def _is_correct(predicted: str, actual: str) -> bool:
        predicted = predicted.upper()
        if predicted == NewsDirection.MIXED.value:
            return actual == NewsDirection.NEUTRAL.value
        if predicted == NewsDirection.UNKNOWN.value:
            return False
        return predicted == actual

    @staticmethod
    def _price_at_or_after(candles: list[Any], target: datetime) -> float | None:
        target = target if target.tzinfo else target.replace(tzinfo=UTC)
        best: tuple[datetime, float] | None = None
        for candle in candles:
            candle_time = getattr(candle, "candle_time", None) or candle.get("candle_time")
            close = getattr(candle, "close", None) if not isinstance(candle, dict) else candle.get("close")
            parsed = NewsImpactValidator._parse_dt(candle_time)
            if parsed is None or close is None or parsed < target:
                continue
            if best is None or parsed < best[0]:
                best = (parsed, float(close))
        return best[1] if best else None

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except Exception:
            return None
