from __future__ import annotations

from typing import Any


class SignalReplayService:
    def build_replay(self, storage, signal_id: int) -> dict[str, Any]:
        signal = storage.get_signal_detail(signal_id) or {}
        snapshot = storage.get_signal_snapshot(signal_id) or {}
        outcome = storage.get_signal_outcome(signal_id) or {
            "recommendation_id": signal_id,
            "outcome": "PENDING",
            "message": "Pending validation",
        }
        raw = snapshot.get("raw_recommendation_json") or signal
        model_votes = snapshot.get("model_votes_json") or raw.get("model_votes") or []
        model_weights = snapshot.get("model_weights_json") or {}
        indicators = snapshot.get("indicator_summary_json") or raw.get("indicator_summary") or {}
        market_regime = snapshot.get("market_regime_json") or snapshot.get("market_structure_json") or {}
        multi_timeframe = snapshot.get("multi_timeframe_summary_json") or {}
        entry_plans = storage.get_signal_entry_plans(signal_id).get("items", []) if hasattr(storage, "get_signal_entry_plans") else []
        return {
            "signal": signal,
            "outcome": outcome,
            "model_votes": model_votes,
            "model_weights": model_weights,
            "indicators": indicators,
            "market_regime": market_regime,
            "multi_timeframe": multi_timeframe,
            "entry_plans": entry_plans,
            "risk_filters": snapshot.get("risk_filters_json") or {},
            "blocked_reasons": snapshot.get("blocked_reasons_json") or raw.get("blocked_reasons") or [],
            "candles_before": [],
            "candles_after": [],
            "raw_snapshot": snapshot,
        }
