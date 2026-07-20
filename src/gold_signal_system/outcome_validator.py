from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .contracts import Candle, FinalRecommendation, SignalDirection


FINAL_OUTCOMES = {
    "WIN",
    "LOSS",
    "PARTIAL_TP",
    "BREAKEVEN",
    "MISSED_ENTRY",
    "EXPIRED",
    "CANCELLED",
    "UNKNOWN",
    "NO_TRADE",
}


@dataclass(slots=True)
class OutcomeValidation:
    outcome_status: str
    entry_triggered: bool
    realized_rr: float
    max_favorable_move: float
    max_adverse_move: float
    validated_at: datetime
    entry_triggered_at: datetime | None = None
    entry_triggered_price: float | None = None
    highest_price_after_signal: float | None = None
    lowest_price_after_signal: float | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl_points: float | None = None
    pnl_percent: float | None = None
    validation_window_candles: int = 0
    ambiguous_candle: bool = False
    timeline: list[dict[str, Any]] | None = None

    @property
    def is_final(self) -> bool:
        return self.outcome_status in FINAL_OUTCOMES

    def model_dump(self) -> dict[str, Any]:
        return {
            "outcome_status": self.outcome_status,
            "entry_triggered": self.entry_triggered,
            "realized_rr": self.realized_rr,
            "max_favorable_move": self.max_favorable_move,
            "max_adverse_move": self.max_adverse_move,
            "validated_at": self.validated_at.isoformat(),
            "entry_triggered_at": self.entry_triggered_at.isoformat() if self.entry_triggered_at else None,
            "entry_triggered_price": self.entry_triggered_price,
            "highest_price_after_signal": self.highest_price_after_signal,
            "lowest_price_after_signal": self.lowest_price_after_signal,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "pnl_points": self.pnl_points,
            "pnl_percent": self.pnl_percent,
            "validation_window_candles": self.validation_window_candles,
            "ambiguous_candle": self.ambiguous_candle,
            "timeline": self.timeline or [],
        }


class SignalOutcomeValidator:
    """Validate whether a recommendation entered, hit TP, hit SL, or expired."""

    def validate(self, recommendation: FinalRecommendation, candles: list[Candle]) -> OutcomeValidation:
        now = datetime.now(tz=UTC)
        if not candles:
            return self._result(recommendation, "PENDING", False, 0.0, 0.0, 0.0, now)

        validated_at = candles[-1].candle_time
        if recommendation.signal == SignalDirection.HOLD or recommendation.entry_price is None or recommendation.stop_loss is None:
            return self._result(recommendation, "NO_TRADE", False, 0.0, 0.0, 0.0, validated_at)

        entry = float(recommendation.entry_price)
        sl = float(recommendation.stop_loss)
        tp1 = float(recommendation.take_profit_1 or entry)
        tp2 = float(recommendation.take_profit_2 or tp1)
        tp3 = float(recommendation.take_profit_3 or tp2)
        risk = abs(entry - sl) or 0.0001
        expiry = recommendation.expiry_time

        future = [c for c in candles if c.candle_time > recommendation.signal_time]
        if not future:
            return self._result(recommendation, "PENDING", False, 0.0, 0.0, 0.0, validated_at)

        entry_triggered = bool(recommendation.entry_triggered)
        max_fav = float(recommendation.max_favorable_move or 0.0)
        max_adv = float(recommendation.max_adverse_move or 0.0)
        entry_triggered_at: datetime | None = None
        entry_triggered_price: float | None = entry if entry_triggered else None
        timeline: list[dict[str, Any]] = []
        highest_price = max(float(c.high) for c in future)
        lowest_price = min(float(c.low) for c in future)
        validation_window = len(future)
        tp1_hit = False

        for candle in future:
            if expiry is not None and candle.candle_time > expiry and not entry_triggered:
                timeline.append({"at": candle.candle_time.isoformat(), "event": "MISSED_ENTRY", "reason": "Entry not touched before expiry."})
                return self._result(
                    recommendation,
                    "MISSED_ENTRY",
                    False,
                    0.0,
                    max_fav,
                    max_adv,
                    candle.candle_time,
                    highest_price_after_signal=highest_price,
                    lowest_price_after_signal=lowest_price,
                    exit_reason="ENTRY_NOT_TRIGGERED_BEFORE_EXPIRY",
                    validation_window_candles=validation_window,
                    timeline=timeline,
                )

            high = float(candle.high)
            low = float(candle.low)

            if not entry_triggered:
                if self._entry_touched(recommendation, high, low):
                    entry_triggered = True
                    entry_triggered_at = candle.candle_time
                    entry_triggered_price = entry
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "ENTRY_TRIGGERED", "price": entry})
                else:
                    continue

            if recommendation.signal == SignalDirection.BUY:
                max_fav = max(max_fav, high - entry)
                max_adv = max(max_adv, entry - low)
                sl_hit = low <= sl
                current_tp1_hit = high >= tp1
                tp1_hit = tp1_hit or current_tp1_hit
                tp2_hit = high >= tp2
                tp3_hit = high >= tp3
                ambiguous = sl_hit and (current_tp1_hit or tp2_hit or tp3_hit)

                if ambiguous:
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "AMBIGUOUS_TP_SL", "conservative_outcome": "LOSS"})
                    return self._closed_result(
                        recommendation, "LOSS", "SL_HIT_AMBIGUOUS", True, -1.0, max_fav, max_adv,
                        candle.candle_time, entry_triggered_at, entry_triggered_price, highest_price, lowest_price,
                        sl, validation_window, ambiguous_candle=True, timeline=timeline,
                    )
                if sl_hit:
                    outcome = "PARTIAL_TP" if tp1_hit else "LOSS"
                    realized_rr = abs(tp1 - entry) / risk if tp1_hit else -1.0
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "SL_HIT", "outcome": outcome})
                    return self._closed_result(
                        recommendation, outcome, "SL_AFTER_TP1" if tp1_hit else "SL_HIT", True, realized_rr,
                        max_fav, max_adv, candle.candle_time, entry_triggered_at, entry_triggered_price,
                        highest_price, lowest_price, sl, validation_window, timeline=timeline,
                    )
                if tp3_hit:
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "TP3_HIT", "outcome": "WIN"})
                    return self._closed_result(
                        recommendation, "WIN", "TP3_HIT", True, abs(tp3 - entry) / risk, max_fav, max_adv,
                        candle.candle_time, entry_triggered_at, entry_triggered_price, highest_price, lowest_price,
                        tp3, validation_window, timeline=timeline,
                    )
                if tp2_hit:
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "TP2_HIT", "outcome": "WIN"})
                    return self._closed_result(
                        recommendation, "WIN", "TP2_HIT", True, abs(tp2 - entry) / risk, max_fav, max_adv,
                        candle.candle_time, entry_triggered_at, entry_triggered_price, highest_price, lowest_price,
                        tp2, validation_window, timeline=timeline,
                    )
            else:
                max_fav = max(max_fav, entry - low)
                max_adv = max(max_adv, high - entry)
                sl_hit = high >= sl
                current_tp1_hit = low <= tp1
                tp1_hit = tp1_hit or current_tp1_hit
                tp2_hit = low <= tp2
                tp3_hit = low <= tp3
                ambiguous = sl_hit and (current_tp1_hit or tp2_hit or tp3_hit)

                if ambiguous:
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "AMBIGUOUS_TP_SL", "conservative_outcome": "LOSS"})
                    return self._closed_result(
                        recommendation, "LOSS", "SL_HIT_AMBIGUOUS", True, -1.0, max_fav, max_adv,
                        candle.candle_time, entry_triggered_at, entry_triggered_price, highest_price, lowest_price,
                        sl, validation_window, ambiguous_candle=True, timeline=timeline,
                    )
                if sl_hit:
                    outcome = "PARTIAL_TP" if tp1_hit else "LOSS"
                    realized_rr = abs(entry - tp1) / risk if tp1_hit else -1.0
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "SL_HIT", "outcome": outcome})
                    return self._closed_result(
                        recommendation, outcome, "SL_AFTER_TP1" if tp1_hit else "SL_HIT", True, realized_rr,
                        max_fav, max_adv, candle.candle_time, entry_triggered_at, entry_triggered_price,
                        highest_price, lowest_price, sl, validation_window, timeline=timeline,
                    )
                if tp3_hit:
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "TP3_HIT", "outcome": "WIN"})
                    return self._closed_result(
                        recommendation, "WIN", "TP3_HIT", True, abs(entry - tp3) / risk, max_fav, max_adv,
                        candle.candle_time, entry_triggered_at, entry_triggered_price, highest_price, lowest_price,
                        tp3, validation_window, timeline=timeline,
                    )
                if tp2_hit:
                    timeline.append({"at": candle.candle_time.isoformat(), "event": "TP2_HIT", "outcome": "WIN"})
                    return self._closed_result(
                        recommendation, "WIN", "TP2_HIT", True, abs(entry - tp2) / risk, max_fav, max_adv,
                        candle.candle_time, entry_triggered_at, entry_triggered_price, highest_price, lowest_price,
                        tp2, validation_window, timeline=timeline,
                    )

            if expiry is not None and candle.candle_time > expiry:
                outcome = "PARTIAL_TP" if tp1_hit else "EXPIRED"
                realized_rr = abs(tp1 - entry) / risk if tp1_hit else 0.0
                timeline.append({"at": candle.candle_time.isoformat(), "event": "EXPIRED", "outcome": outcome})
                return self._closed_result(
                    recommendation, outcome, "TP1_ONLY_EXPIRED" if tp1_hit else "EXPIRED", True, realized_rr,
                    max_fav, max_adv, candle.candle_time, entry_triggered_at, entry_triggered_price,
                    highest_price, lowest_price, None, validation_window, timeline=timeline,
                )

        status = "ENTRY_TRIGGERED" if entry_triggered else "WAITING_FOR_ENTRY"
        if expiry is not None and validated_at > expiry and not entry_triggered:
            status = "MISSED_ENTRY"
        elif expiry is not None and validated_at > expiry and entry_triggered:
            status = "EXPIRED"

        return self._result(
            recommendation,
            status,
            entry_triggered,
            0.0,
            max_fav,
            max_adv,
            validated_at,
            entry_triggered_at=entry_triggered_at,
            entry_triggered_price=entry_triggered_price,
            highest_price_after_signal=highest_price,
            lowest_price_after_signal=lowest_price,
            validation_window_candles=validation_window,
            timeline=timeline,
        )

    def _entry_touched(self, recommendation: FinalRecommendation, high: float, low: float) -> bool:
        if recommendation.entry_type is not None and recommendation.entry_type.value == "MARKET":
            return True
        entry = float(recommendation.entry_price or 0.0)
        return low <= entry <= high

    def _result(
        self,
        recommendation: FinalRecommendation,
        outcome: str,
        entry_triggered: bool,
        realized_rr: float,
        max_fav: float,
        max_adv: float,
        validated_at: datetime,
        entry_triggered_at: datetime | None = None,
        entry_triggered_price: float | None = None,
        highest_price_after_signal: float | None = None,
        lowest_price_after_signal: float | None = None,
        exit_price: float | None = None,
        exit_reason: str | None = None,
        pnl_points: float | None = None,
        pnl_percent: float | None = None,
        validation_window_candles: int = 0,
        ambiguous_candle: bool = False,
        timeline: list[dict[str, Any]] | None = None,
    ) -> OutcomeValidation:
        if validated_at.tzinfo is None:
            validated_at = validated_at.replace(tzinfo=UTC)
        if entry_triggered_at is not None and entry_triggered_at.tzinfo is None:
            entry_triggered_at = entry_triggered_at.replace(tzinfo=UTC)
        return OutcomeValidation(
            outcome_status=outcome,
            entry_triggered=entry_triggered,
            realized_rr=round(float(realized_rr), 4),
            max_favorable_move=round(float(max_fav), 4),
            max_adverse_move=round(float(max_adv), 4),
            validated_at=validated_at.astimezone(UTC),
            entry_triggered_at=entry_triggered_at.astimezone(UTC) if entry_triggered_at else None,
            entry_triggered_price=entry_triggered_price,
            highest_price_after_signal=highest_price_after_signal,
            lowest_price_after_signal=lowest_price_after_signal,
            exit_price=exit_price,
            exit_reason=exit_reason,
            pnl_points=pnl_points,
            pnl_percent=pnl_percent,
            validation_window_candles=validation_window_candles,
            ambiguous_candle=ambiguous_candle,
            timeline=timeline or [],
        )

    def _closed_result(
        self,
        recommendation: FinalRecommendation,
        outcome: str,
        exit_reason: str,
        entry_triggered: bool,
        realized_rr: float,
        max_fav: float,
        max_adv: float,
        validated_at: datetime,
        entry_triggered_at: datetime | None,
        entry_triggered_price: float | None,
        highest_price_after_signal: float,
        lowest_price_after_signal: float,
        exit_price: float | None,
        validation_window_candles: int,
        ambiguous_candle: bool = False,
        timeline: list[dict[str, Any]] | None = None,
    ) -> OutcomeValidation:
        entry = float(recommendation.entry_price or 0.0)
        pnl_points = None
        pnl_percent = None
        if exit_price is not None and entry:
            if recommendation.signal == SignalDirection.BUY:
                pnl_points = exit_price - entry
            else:
                pnl_points = entry - exit_price
            pnl_percent = (pnl_points / entry) * 100.0

        return self._result(
            recommendation,
            outcome,
            entry_triggered,
            realized_rr,
            max_fav,
            max_adv,
            validated_at,
            entry_triggered_at=entry_triggered_at,
            entry_triggered_price=entry_triggered_price,
            highest_price_after_signal=highest_price_after_signal,
            lowest_price_after_signal=lowest_price_after_signal,
            exit_price=exit_price,
            exit_reason=exit_reason,
            pnl_points=round(pnl_points, 4) if pnl_points is not None else None,
            pnl_percent=round(pnl_percent, 4) if pnl_percent is not None else None,
            validation_window_candles=validation_window_candles,
            ambiguous_candle=ambiguous_candle,
            timeline=timeline,
        )
