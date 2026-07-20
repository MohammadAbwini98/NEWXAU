from __future__ import annotations

from dateutil import parser
from datetime import UTC, datetime
from typing import Any

from .contracts import FinalRecommendation, MarketContext
from .pipeline import GoldSignalSystem
from .storage import SignalOutcome


class PaperTradingEngine:
    """Phase 9: live-like signal generation and outcome tracking without real execution."""

    def __init__(self, system: GoldSignalSystem) -> None:
        self.system = system
        self.cycles: list[dict[str, Any]] = []

    def run_cycle(self, candles: list[dict], source_timeframe: str = "1m") -> dict[str, Any]:
        context = MarketContext()
        result = self.system.run_signal_cycle(candles, source_timeframe=source_timeframe, market_context=context)
        rec = result.recommendation
        recommendation_id = len(self.system.storage.trade_recommendations)

        record = {
            "cycle_time": datetime.now(tz=UTC).isoformat(),
            "recommendation_id": recommendation_id,
            "recommendation": rec.model_dump(mode="json"),
            "status": rec.status.value,
            "signal": rec.signal.value,
            "confidence": rec.confidence,
        }
        self.cycles.append(record)
        return record

    def track_outcome(self, recommendation_id: int, outcome: dict[str, Any]) -> None:
        closed_at_raw = outcome.get("closed_at")
        if closed_at_raw:
            try:
                closed_at = parser.isoparse(str(closed_at_raw))
            except Exception:
                closed_at = datetime.now(tz=UTC)
        else:
            closed_at = datetime.now(tz=UTC)

        signal_outcome = SignalOutcome(
            recommendation_id=recommendation_id,
            outcome=str(outcome.get("outcome", "UNKNOWN")),
            entry_triggered=bool(outcome.get("entry_triggered", True)),
            hit_tp1=bool(outcome.get("hit_tp1", False)),
            hit_tp2=bool(outcome.get("hit_tp2", False)),
            hit_tp3=bool(outcome.get("hit_tp3", False)),
            hit_sl=bool(outcome.get("hit_sl", False)),
            max_favorable_move=float(outcome.get("max_favorable_move", 0.0) or 0.0),
            max_adverse_move=float(outcome.get("max_adverse_move", 0.0) or 0.0),
            realized_rr=float(outcome.get("realized_rr", 0.0) or 0.0),
            closed_at=closed_at,
            raw_json={
                "source": "paper",
                "payload": outcome,
                "tracked_at": datetime.now(tz=UTC).isoformat(),
            },
        )
        self.system.storage.save_outcome(signal_outcome)

        recommendation_payload = self.system.storage.get_signal_detail(recommendation_id)
        if recommendation_payload:
            recommendation = FinalRecommendation.model_validate(recommendation_payload)
            recommendation.outcome_status = signal_outcome.outcome
            recommendation.entry_triggered = signal_outcome.entry_triggered
            recommendation.realized_rr = signal_outcome.realized_rr
            recommendation.max_favorable_move = signal_outcome.max_favorable_move
            recommendation.max_adverse_move = signal_outcome.max_adverse_move
            recommendation.outcome_validated_at = signal_outcome.closed_at
            self.system.storage.update_recommendation(recommendation_id, recommendation)
            self.system.record_model_outcome(
                recommendation=recommendation,
                realized_rr=signal_outcome.realized_rr,
                outcome=signal_outcome.outcome,
                source="paper",
            )

    def drift_report(self) -> dict[str, Any]:
        if not self.cycles:
            return {"cycles": 0, "drift_status": "NO_DATA"}

        avg_conf = sum(c["confidence"] for c in self.cycles) / len(self.cycles)
        hold_ratio = sum(1 for c in self.cycles if c["signal"] == "HOLD") / len(self.cycles)

        drift_status = "NORMAL"
        if hold_ratio > 0.7:
            drift_status = "HIGH_HOLD_RATIO"
        if avg_conf < 0.55:
            drift_status = "LOW_CONFIDENCE_DRIFT"

        return {
            "cycles": len(self.cycles),
            "average_confidence": round(avg_conf, 4),
            "hold_ratio": round(hold_ratio, 4),
            "drift_status": drift_status,
        }
