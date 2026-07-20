from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

from .contracts import (
    Candle,
    EnsemblePrediction,
    FinalRecommendation,
    IndicatorSnapshot,
    ModelPrediction,
    RiskCheck,
    StrategyDecision,
)
from .market_sessions import normalize_gold_session_name


_SESSION_FILTER_ALIASES: dict[str, tuple[str, ...]] = {
    "ASIA_LOW": ("ASIA_LOW", "ASIA", "ASIAN", "ASIAN_SESSION", "ASIA_SESSION"),
    "LONDON_ACTIVE": ("LONDON_ACTIVE", "LONDON", "LONDON_SESSION"),
    "NY_ACTIVE": ("NY_ACTIVE", "NY", "NEWYORK", "NEW_YORK", "NEW_YORK_SESSION"),
    "US_OVERLAP": (
        "US_OVERLAP",
        "US",
        "US_SESSION",
        "OVERLAP",
        "LONDON_NEW_YORK",
        "LONDON_NEW_YORK_OVERLAP",
        "LONDON_NY",
        "LONDON_NY_OVERLAP",
        "LONDON_NEWYORK_OVERLAP",
    ),
    "DAILY_BREAK": ("DAILY_BREAK", "ROLLOVER", "ROLLOVER_SESSION", "BREAK", "DAILY_ROLLOVER"),
}


def _execution_order_market_session(order: dict[str, Any]) -> str:
    request_json = order.get("request_json") or {}
    if not isinstance(request_json, dict):
        return "UNKNOWN"
    recommendation = request_json.get("recommendation") or {}
    if not isinstance(recommendation, dict):
        return "UNKNOWN"
    return _recommendation_market_session(recommendation)


def _execution_order_session_from_payload(order: dict[str, Any]) -> str:
    existing = normalize_gold_session_name(order.get("market_session"))
    if existing != "UNKNOWN":
        return existing
    session = _execution_order_market_session(order)
    if session != "UNKNOWN":
        return session
    recommendation_raw = order.get("recommendation_raw_json")
    if isinstance(recommendation_raw, dict):
        return _recommendation_market_session(recommendation_raw)
    raw = order.get("market_session_raw")
    session = normalize_gold_session_name(raw)
    return session if session != "UNKNOWN" else "UNKNOWN"


def _annotate_execution_order_session(order: dict[str, Any], session: str | None = None) -> dict[str, Any]:
    clean = {key: value for key, value in order.items() if key not in {"market_session_raw", "recommendation_raw_json"}}
    clean["market_session"] = session or _execution_order_session_from_payload(order)
    return clean


def _recommendation_market_session(recommendation: dict[str, Any] | FinalRecommendation | None) -> str:
    if recommendation is None:
        return "UNKNOWN"
    if isinstance(recommendation, FinalRecommendation):
        summary = recommendation.indicator_summary or {}
    elif isinstance(recommendation, dict):
        summary = recommendation.get("indicator_summary") or {}
    else:
        return "UNKNOWN"
    if not isinstance(summary, dict):
        return "UNKNOWN"
    raw_json = summary.get("raw_json") if isinstance(summary.get("raw_json"), dict) else {}
    for candidate in (
        summary.get("session"),
        summary.get("session_name"),
        summary.get("market_session"),
        raw_json.get("session"),
        raw_json.get("session_name"),
        raw_json.get("market_session"),
    ):
        session = normalize_gold_session_name(candidate)
        if session != "UNKNOWN":
            return session
    return "UNKNOWN"


def _normalized_session_filter(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip().upper()
    if text == "UNKNOWN":
        return "UNKNOWN"
    normalized = normalize_gold_session_name(text)
    return normalized if normalized != "UNKNOWN" else None


def _count_values(rows: list[dict[str, Any]], key: str, default: str = "UNKNOWN") -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or default).upper()
        counts[value] = counts.get(value, 0) + 1
    return counts


def _execution_order_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    annotated = [_annotate_execution_order_session(row) for row in rows]
    outcomes = _count_values(annotated, "outcome", "PENDING")
    statuses = _count_values(annotated, "status")
    directions = _count_values(annotated, "direction")
    sessions = _count_values(annotated, "market_session")
    wins = int(outcomes.get("WIN", 0))
    losses = int(outcomes.get("LOSS", 0))
    decided = wins + losses
    return {
        "total": len(annotated),
        "by_status": statuses,
        "by_outcome": outcomes,
        "by_direction": directions,
        "by_session": sessions,
        "wins": wins,
        "losses": losses,
        "pending": int(outcomes.get("PENDING", 0)),
        "confirmed": int(statuses.get("CONFIRMED", 0)),
        "rejected": int(statuses.get("REJECTED", 0)),
        "win_rate": round(wins / decided, 4) if decided else None,
    }


@dataclass(slots=True)
class SignalOutcome:
    recommendation_id: int
    outcome: str
    entry_triggered: bool
    hit_tp1: bool
    hit_tp2: bool
    hit_tp3: bool
    hit_sl: bool
    max_favorable_move: float
    max_adverse_move: float
    realized_rr: float
    closed_at: datetime
    raw_json: dict[str, Any] = field(default_factory=dict)
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


@dataclass(slots=True)
class SignalSnapshot:
    signal_id: int
    model_votes_json: list[dict[str, Any]]
    model_weights_json: dict[str, float]
    indicator_summary_json: dict[str, Any]
    market_structure_json: dict[str, Any]
    risk_filters_json: dict[str, Any]
    blocked_reasons_json: list[str]
    entry_plan_json: dict[str, Any]
    raw_recommendation_json: dict[str, Any]
    market_regime_json: dict[str, Any] = field(default_factory=dict)
    multi_timeframe_summary_json: dict[str, Any] = field(default_factory=dict)
    dynamic_weights_json: dict[str, Any] = field(default_factory=dict)
    entry_plans_json: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    except Exception:
        return None


class InMemoryStorage:
    """In-memory persistence layer that mirrors database tables for local execution."""

    def __init__(self) -> None:
        self.market_candles: list[Candle] = []
        self.indicator_snapshots: list[IndicatorSnapshot] = []
        self.model_predictions: list[ModelPrediction] = []
        self.ensemble_predictions: list[EnsemblePrediction] = []
        self.strategy_decisions: list[StrategyDecision] = []
        self.trade_recommendations: list[FinalRecommendation] = []
        self.signal_snapshots: list[SignalSnapshot] = []
        self.risk_checks: list[RiskCheck] = []
        self.signal_outcomes: list[SignalOutcome] = []
        self.model_signal_predictions: list[dict[str, Any]] = []
        self.model_prediction_outcomes: list[dict[str, Any]] = []
        self.signal_entry_plans: list[dict[str, Any]] = []
        self.market_regimes: list[dict[str, Any]] = []
        self.timeframe_confirmations: list[dict[str, Any]] = []
        self.news_events: list[dict[str, Any]] = []
        self.system_health_events: list[dict[str, Any]] = []
        self.optimization_runs: list[dict[str, Any]] = []
        self.strategy_profiles: list[dict[str, Any]] = []
        self.backtest_runs: list[dict[str, Any]] = []
        self.backtest_trades: list[dict[str, Any]] = []
        self.execution_orders: list[dict[str, Any]] = []
        self.execution_control_decisions: list[dict[str, Any]] = []
        self.execution_account_snapshots: list[dict[str, Any]] = []
        self.model_performance: list[dict[str, Any]] = []
        self.system_settings: dict[str, Any] = {}
        self._last_recommendation_id: int | None = None

    def save_candles(self, candles: list[Candle]) -> None:
        self.market_candles.extend(candles)

    def save_indicator_snapshot(self, snapshot: IndicatorSnapshot) -> None:
        self.indicator_snapshots.append(snapshot)

    def save_model_predictions(self, predictions: list[ModelPrediction]) -> None:
        self.model_predictions.extend(predictions)

    def save_ensemble_prediction(self, prediction: EnsemblePrediction) -> None:
        self.ensemble_predictions.append(prediction)

    def save_strategy_decision(self, decision: StrategyDecision) -> None:
        self.strategy_decisions.append(decision)

    def save_recommendation(self, recommendation: FinalRecommendation) -> int:
        self.trade_recommendations.append(recommendation)
        rec_id = len(self.trade_recommendations)
        self._last_recommendation_id = rec_id
        return rec_id

    def save_risk_check(self, risk_check: RiskCheck) -> None:
        self.risk_checks.append(risk_check)

    def save_outcome(self, outcome: SignalOutcome) -> None:
        self.signal_outcomes.append(outcome)

    def save_signal_snapshot(self, snapshot: SignalSnapshot) -> None:
        self.signal_snapshots = [item for item in self.signal_snapshots if item.signal_id != snapshot.signal_id]
        self.signal_snapshots.append(snapshot)

    def save_model_signal_predictions(
        self,
        signal_id: int,
        predictions: list[ModelPrediction],
        weights: dict[str, float],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for prediction in predictions:
            key = prediction.model_name.lower()
            row = {
                "id": len(self.model_signal_predictions) + len(rows) + 1,
                "signal_id": signal_id,
                "model_name": prediction.model_name,
                "model_version": prediction.model_version,
                "instrument": prediction.instrument,
                "timeframe": prediction.timeframe,
                "predicted_signal": prediction.signal.value,
                "confidence": prediction.confidence,
                "raw_score": max(prediction.buy_probability, prediction.sell_probability, prediction.hold_probability),
                "predicted_return": prediction.expected_return,
                "predicted_high": None,
                "predicted_low": None,
                "forecast_horizon": prediction.prediction_horizon_candles,
                "weight_used": weights.get(key, 0.0),
                "created_at": prediction.prediction_time.isoformat(),
            }
            rows.append(row)
        self.model_signal_predictions.extend(rows)
        return rows

    def save_model_prediction_outcomes(
        self,
        signal_id: int,
        recommendation: FinalRecommendation,
        outcome: SignalOutcome,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        actual_profitable = outcome.realized_rr > 0
        for prediction_row in self.model_signal_predictions:
            if prediction_row.get("signal_id") != signal_id:
                continue
            predicted_signal = prediction_row.get("predicted_signal")
            direction_correct = (
                predicted_signal == recommendation.signal.value
                and recommendation.signal.value in {"BUY", "SELL"}
                and actual_profitable
            ) or (
                predicted_signal == "HOLD"
                and recommendation.signal.value == "HOLD"
            )
            actual_return = outcome.pnl_points if outcome.pnl_points is not None else outcome.realized_rr
            predicted_return = float(prediction_row.get("predicted_return") or 0.0)
            error = abs(predicted_return - float(actual_return or 0.0))
            row = {
                "id": len(self.model_prediction_outcomes) + len(rows) + 1,
                "model_prediction_id": prediction_row["id"],
                "signal_id": signal_id,
                "model_name": prediction_row["model_name"],
                "was_direction_correct": direction_correct,
                "was_profitable": actual_profitable,
                "actual_outcome": outcome.outcome,
                "actual_return": actual_return,
                "error_abs": error,
                "error_squared": error * error,
                "evaluated_at": outcome.closed_at.isoformat(),
            }
            rows.append(row)
        self.model_prediction_outcomes.extend(rows)
        return rows

    def save_signal_entry_plans(self, signal_id: int, plans: list[dict[str, Any]]) -> None:
        self.signal_entry_plans = [item for item in self.signal_entry_plans if item.get("signal_id") != signal_id]
        for plan in plans:
            self.signal_entry_plans.append({"signal_id": signal_id, **plan})

    def get_signal_entry_plans(self, signal_id: int) -> dict[str, Any]:
        items = [item for item in self.signal_entry_plans if item.get("signal_id") == signal_id]
        return {"total": len(items), "items": items}

    def get_selected_entry_plan(self, signal_id: int) -> dict[str, Any]:
        plans = self.get_signal_entry_plans(signal_id)["items"]
        return next((item for item in plans if item.get("selected")), {})

    def save_market_regime(self, signal_id: int | None, regime: dict[str, Any]) -> None:
        self.market_regimes.append({"signal_id": signal_id, **regime})

    def latest_market_regime(self, timeframe: str | None = None) -> dict[str, Any]:
        return self.market_regimes[-1] if self.market_regimes else {"primary_regime": "UNKNOWN", "reasoning": ["Waiting for regime calculation."]}

    def get_signal_regime(self, signal_id: int) -> dict[str, Any]:
        for item in reversed(self.market_regimes):
            if item.get("signal_id") == signal_id:
                return item
        snapshot = self.get_signal_snapshot(signal_id) or {}
        return snapshot.get("market_regime_json", {})

    def save_timeframe_confirmation(self, signal_id: int | None, confirmation: dict[str, Any]) -> None:
        self.timeframe_confirmations.append({"signal_id": signal_id, **confirmation})

    def latest_timeframe_confirmation(self) -> dict[str, Any]:
        return self.timeframe_confirmations[-1] if self.timeframe_confirmations else {"status": "INSUFFICIENT_DATA"}

    def get_signal_timeframe_confirmation(self, signal_id: int) -> dict[str, Any]:
        for item in reversed(self.timeframe_confirmations):
            if item.get("signal_id") == signal_id:
                return item
        snapshot = self.get_signal_snapshot(signal_id) or {}
        return snapshot.get("multi_timeframe_summary_json", {})

    def update_recommendation(self, recommendation_id: int, recommendation: FinalRecommendation) -> None:
        idx = recommendation_id - 1
        if idx < 0 or idx >= len(self.trade_recommendations):
            return
        self.trade_recommendations[idx] = recommendation

    def list_recommendations_with_ids(self) -> list[tuple[int, FinalRecommendation]]:
        return [(idx, rec) for idx, rec in enumerate(self.trade_recommendations, start=1)]

    def get_signal_outcomes(self, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        rows = list(self.signal_outcomes)
        rows.sort(key=lambda r: r.closed_at, reverse=True)
        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return {
            "total": len(rows),
            "page": safe_page,
            "page_size": safe_page_size,
            "items": [
                {
                    "recommendation_id": item.recommendation_id,
                    "outcome": item.outcome,
                    "entry_triggered": item.entry_triggered,
                    "hit_tp1": item.hit_tp1,
                    "hit_tp2": item.hit_tp2,
                    "hit_tp3": item.hit_tp3,
                    "hit_sl": item.hit_sl,
                    "max_favorable_move": item.max_favorable_move,
                    "max_adverse_move": item.max_adverse_move,
                    "realized_rr": item.realized_rr,
                    "closed_at": item.closed_at.isoformat(),
                    "raw_json": item.raw_json,
                    "entry_triggered_at": item.entry_triggered_at.isoformat() if item.entry_triggered_at else None,
                    "entry_triggered_price": item.entry_triggered_price,
                    "highest_price_after_signal": item.highest_price_after_signal,
                    "lowest_price_after_signal": item.lowest_price_after_signal,
                    "exit_price": item.exit_price,
                    "exit_reason": item.exit_reason,
                    "pnl_points": item.pnl_points,
                    "pnl_percent": item.pnl_percent,
                    "validation_window_candles": item.validation_window_candles,
                    "ambiguous_candle": item.ambiguous_candle,
                }
                for item in rows[start:end]
            ],
        }

    def get_signal_outcome(self, signal_id: int) -> dict[str, Any] | None:
        matches = [item for item in self.signal_outcomes if item.recommendation_id == signal_id]
        if not matches:
            return None
        item = sorted(matches, key=lambda row: row.closed_at, reverse=True)[0]
        return {
            "recommendation_id": item.recommendation_id,
            "outcome": item.outcome,
            "entry_triggered": item.entry_triggered,
            "hit_tp1": item.hit_tp1,
            "hit_tp2": item.hit_tp2,
            "hit_tp3": item.hit_tp3,
            "hit_sl": item.hit_sl,
            "max_favorable_move": item.max_favorable_move,
            "max_adverse_move": item.max_adverse_move,
            "realized_rr": item.realized_rr,
            "closed_at": item.closed_at.isoformat(),
            "raw_json": item.raw_json,
            "entry_triggered_at": item.entry_triggered_at.isoformat() if item.entry_triggered_at else None,
            "entry_triggered_price": item.entry_triggered_price,
            "highest_price_after_signal": item.highest_price_after_signal,
            "lowest_price_after_signal": item.lowest_price_after_signal,
            "exit_price": item.exit_price,
            "exit_reason": item.exit_reason,
            "pnl_points": item.pnl_points,
            "pnl_percent": item.pnl_percent,
            "validation_window_candles": item.validation_window_candles,
            "ambiguous_candle": item.ambiguous_candle,
        }

    def latest_recommendation(self) -> FinalRecommendation | None:
        if not self.trade_recommendations:
            return None
        return self.trade_recommendations[-1]

    def latest_recommendation_id(self) -> int | None:
        return self._last_recommendation_id

    def get_execution_order_by_signal(self, signal_id: int) -> dict[str, Any] | None:
        matches = [item for item in self.execution_orders if int(item.get("signal_id") or 0) == int(signal_id)]
        if not matches:
            return None
        matches.sort(key=lambda item: item.get("requested_at") or item.get("created_at") or "", reverse=True)
        return matches[0]

    def get_execution_order_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        return next((item for item in self.execution_orders if item.get("idempotency_key") == idempotency_key), None)

    def create_execution_order(self, order: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(tz=UTC).isoformat()
        payload = {
            "id": len(self.execution_orders) + 1,
            "requested_at": now,
            "created_at": now,
            "updated_at": now,
            "request_json": {},
            "response_json": {},
            "confirm_json": {},
            "outcome": "PENDING",
            **order,
        }
        existing = next((item for item in self.execution_orders if item.get("idempotency_key") == payload.get("idempotency_key")), None)
        if existing:
            existing.update({key: value for key, value in payload.items() if key != "id"})
            existing["updated_at"] = now
            return existing
        self.execution_orders.append(payload)
        return payload

    def update_execution_order(self, idempotency_key: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        now = datetime.now(tz=UTC).isoformat()
        order = next((item for item in self.execution_orders if item.get("idempotency_key") == idempotency_key), None)
        if not order:
            return None
        order.update(updates)
        order["updated_at"] = now
        return order

    def list_execution_orders(
        self,
        limit: int = 100,
        page: int = 1,
        page_size: int | None = None,
        status: str | None = None,
        outcome: str | None = None,
        direction: str | None = None,
        market_session: str | None = None,
        from_time: datetime | str | None = None,
        to_time: datetime | str | None = None,
        signal_id: int | None = None,
        executed_only: bool = False,
    ) -> dict[str, Any]:
        rows = list(self.execution_orders)
        if executed_only:
            rows = [item for item in rows if item.get("status") in {"READY", "SUBMITTED", "CONFIRMED", "REJECTED"} or item.get("deal_reference") or item.get("deal_id")]
        if status:
            rows = [item for item in rows if str(item.get("status") or "").upper() == status.upper()]
        if outcome:
            rows = [item for item in rows if str(item.get("outcome") or "PENDING").upper() == outcome.upper()]
        if direction:
            rows = [item for item in rows if str(item.get("direction") or "").upper() == direction.upper()]
        session_filter = _normalized_session_filter(market_session)
        if session_filter:
            rows = [item for item in rows if self._execution_order_session(item) == session_filter]
        parsed_from = _parse_dt(from_time)
        if parsed_from:
            rows = [item for item in rows if (_parse_dt(item.get("requested_at") or item.get("created_at")) or datetime.min.replace(tzinfo=UTC)) >= parsed_from]
        parsed_to = _parse_dt(to_time)
        if parsed_to:
            rows = [item for item in rows if (_parse_dt(item.get("requested_at") or item.get("created_at")) or datetime.max.replace(tzinfo=UTC)) <= parsed_to]
        if signal_id is not None:
            rows = [item for item in rows if int(item.get("signal_id") or 0) == int(signal_id)]
        rows.sort(key=lambda item: item.get("requested_at") or item.get("created_at") or "", reverse=True)
        statistics = _execution_order_statistics([{**item, "market_session": self._execution_order_session(item)} for item in rows])
        safe_page = max(int(page or 1), 1)
        safe_page_size = max(int(page_size or limit or 100), 1)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        items = [_annotate_execution_order_session(item, self._execution_order_session(item)) for item in rows[start:end]]
        return {
            "items": items,
            "total": len(rows),
            "page": safe_page,
            "page_size": safe_page_size,
            "statistics": statistics,
        }

    def _execution_order_session(self, order: dict[str, Any]) -> str:
        session = _execution_order_market_session(order)
        if session != "UNKNOWN":
            return session
        try:
            signal_id = int(order.get("signal_id") or 0)
        except (TypeError, ValueError):
            return "UNKNOWN"
        idx = signal_id - 1
        if idx < 0 or idx >= len(self.trade_recommendations):
            return "UNKNOWN"
        return _recommendation_market_session(self.trade_recommendations[idx])

    def save_execution_control_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": len(self.execution_control_decisions) + 1,
            "created_at": datetime.now(tz=UTC).isoformat(),
            **decision,
        }
        self.execution_control_decisions.append(payload)
        return payload

    def list_execution_control_decisions(self, limit: int = 5000) -> dict[str, Any]:
        rows = list(self.execution_control_decisions)
        rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        safe_limit = max(int(limit or 5000), 1)
        return {"items": rows[:safe_limit], "total": len(rows)}

    def save_execution_account_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "id": len(self.execution_account_snapshots) + 1,
            "created_at": datetime.now(tz=UTC).isoformat(),
            **snapshot,
        }
        self.execution_account_snapshots.append(payload)
        return payload

    def latest_execution_account_snapshot(self, account_name: str | None = None) -> dict[str, Any] | None:
        rows = list(self.execution_account_snapshots)
        if account_name:
            rows = [item for item in rows if str(item.get("account_name") or "").lower() == account_name.lower()]
        rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return rows[0] if rows else None

    def latest_model_votes(self, timeframe: str | None = None) -> list[ModelPrediction]:
        if not self.model_predictions:
            return []
        latest_time = max(p.prediction_time for p in self.model_predictions)
        return [p for p in self.model_predictions if p.prediction_time == latest_time and (not timeframe or p.timeframe == timeframe)]

    def latest_indicator_snapshot(self, timeframe: str | None = None) -> IndicatorSnapshot | None:
        return self.indicator_snapshots[-1] if self.indicator_snapshots else None

    def latest_risk_check(self, timeframe: str | None = None) -> RiskCheck | None:
        return self.risk_checks[-1] if self.risk_checks else None

    def get_signal_history(
        self,
        status: str | None = None,
        signal: str | None = None,
        timeframe: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        outcome: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        rows = list(enumerate(self.trade_recommendations, start=1))

        if status:
            rows = [(idx, r) for idx, r in rows if r.status.value == status]
        if signal:
            rows = [(idx, r) for idx, r in rows if r.signal.value == signal]
        if timeframe:
            rows = [(idx, r) for idx, r in rows if r.timeframe == timeframe]
        if from_time:
            rows = [(idx, r) for idx, r in rows if r.signal_time >= from_time]
        if to_time:
            rows = [(idx, r) for idx, r in rows if r.signal_time <= to_time]
        if outcome:
            rows = [(idx, r) for idx, r in rows if getattr(getattr(r, "outcome_status", None), "value", getattr(r, "outcome_status", None)) == outcome]

        rows.sort(key=lambda item: item[1].signal_time, reverse=True)
        total = len(rows)
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), 200)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size

        items: list[dict[str, Any]] = []
        for rec_id, rec in rows[start:end]:
            payload = rec.model_dump(mode="json")
            payload.setdefault("id", rec_id)
            items.append(payload)

        return {
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
            "items": items,
        }

    def get_signal_detail(self, signal_id: int) -> dict[str, Any] | None:
        idx = signal_id - 1
        if idx < 0 or idx >= len(self.trade_recommendations):
            return None
        payload = self.trade_recommendations[idx].model_dump(mode="json")
        payload.setdefault("id", signal_id)
        return payload

    def get_signal_snapshot(self, signal_id: int) -> dict[str, Any] | None:
        for snapshot in reversed(self.signal_snapshots):
            if snapshot.signal_id != signal_id:
                continue
            return {
                "signal_id": snapshot.signal_id,
                "model_votes_json": snapshot.model_votes_json,
                "model_weights_json": snapshot.model_weights_json,
                "indicator_summary_json": snapshot.indicator_summary_json,
                "market_structure_json": snapshot.market_structure_json,
                "risk_filters_json": snapshot.risk_filters_json,
                "blocked_reasons_json": snapshot.blocked_reasons_json,
                "entry_plan_json": snapshot.entry_plan_json,
                "raw_recommendation_json": snapshot.raw_recommendation_json,
                "market_regime_json": snapshot.market_regime_json,
                "multi_timeframe_summary_json": snapshot.multi_timeframe_summary_json,
                "dynamic_weights_json": snapshot.dynamic_weights_json,
                "entry_plans_json": snapshot.entry_plans_json,
                "created_at": snapshot.created_at.isoformat(),
            }
        return None

    def save_model_performance_snapshot(
        self,
        metrics: dict[str, dict[str, Any]],
        weights: dict[str, float],
        source: str,
        timeframe: str,
    ) -> None:
        record = {
            "captured_at": datetime.now(tz=UTC).isoformat(),
            "source": source,
            "timeframe": timeframe,
            "metrics": metrics,
            "weights": weights,
        }
        self.model_performance.append(record)
        self.system_settings["dynamic_model_weights"] = weights

    def create_backtest_run(
        self,
        run_id: str,
        run_type: str,
        instrument: str,
        timeframe: str,
        config_json: dict[str, Any],
        status: str = "RUNNING",
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        started_at = started_at or datetime.now(tz=UTC)
        record = {
            "id": len(self.backtest_runs) + 1,
            "run_id": run_id,
            "run_type": run_type,
            "instrument": instrument,
            "timeframe": timeframe,
            "status": status,
            "started_at": started_at.isoformat(),
            "completed_at": None,
            "config_json": config_json,
            "summary_json": {},
            "report_path": None,
            "error_message": None,
            "created_at": started_at.isoformat(),
            "updated_at": started_at.isoformat(),
        }
        self.backtest_runs = [item for item in self.backtest_runs if item.get("run_id") != run_id]
        self.backtest_runs.append(record)
        return record

    def update_backtest_run(
        self,
        run_id: str,
        status: str,
        summary_json: dict[str, Any] | None = None,
        report_path: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(tz=UTC)
        completed_at = completed_at or (now if status in {"COMPLETED", "FAILED", "CANCELLED"} else None)
        record = next((item for item in self.backtest_runs if item.get("run_id") == run_id), None)
        if record is None:
            record = self.create_backtest_run(run_id, "BACKTEST", "XAUUSD", "1m", {}, status=status)
        record.update(
            {
                "status": status,
                "summary_json": summary_json if summary_json is not None else record.get("summary_json", {}),
                "report_path": report_path if report_path is not None else record.get("report_path"),
                "error_message": error_message,
                "completed_at": completed_at.isoformat() if completed_at else record.get("completed_at"),
                "updated_at": now.isoformat(),
            }
        )
        return record

    def save_backtest_trades(self, run_id: str, trades: list[dict[str, Any]]) -> None:
        self.backtest_trades = [item for item in self.backtest_trades if item.get("run_id") != run_id]
        for idx, trade in enumerate(trades, start=1):
            self.backtest_trades.append(self._normalize_backtest_trade(run_id, trade, idx))

    def save_backtest_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        self.system_settings.setdefault("backtest_metrics", {})[run_id] = metrics

    def save_walk_forward_run(
        self,
        run_id: str,
        instrument: str,
        timeframe: str,
        status: str,
        config_json: dict[str, Any],
        summary_json: dict[str, Any],
        report_path: str | None,
        started_at: datetime | str | None = None,
        completed_at: datetime | str | None = None,
        error_message: str | None = None,
    ) -> None:
        wf_runs = self.system_settings.setdefault("walk_forward_runs", [])
        wf_runs[:] = [item for item in wf_runs if item.get("run_id") != run_id]
        wf_runs.append(
            {
                "run_id": run_id,
                "instrument": instrument,
                "timeframe": timeframe,
                "status": status,
                "started_at": started_at.isoformat() if isinstance(started_at, datetime) else started_at,
                "completed_at": completed_at.isoformat() if isinstance(completed_at, datetime) else completed_at,
                "config_json": config_json,
                "summary_json": summary_json,
                "report_path": report_path,
                "error_message": error_message,
            }
        )

    def save_walk_forward_folds(self, run_id: str, folds: list[dict[str, Any]]) -> None:
        all_folds = self.system_settings.setdefault("walk_forward_folds", [])
        all_folds[:] = [item for item in all_folds if item.get("run_id") != run_id]
        for idx, fold in enumerate(folds, start=1):
            summary = fold.get("summary") or fold.get("metrics_json") or {}
            all_folds.append(
                {
                    "run_id": run_id,
                    "fold_number": int(fold.get("window_id") or fold.get("fold_number") or idx),
                    "train_start": fold.get("train_start"),
                    "train_end": fold.get("train_end"),
                    "test_start": fold.get("test_start"),
                    "test_end": fold.get("test_end"),
                    "status": fold.get("status", "COMPLETED"),
                    "metrics_json": summary,
                    "report_path": fold.get("report_path"),
                }
            )

    def save_walk_forward_reports(self, run_id: str, reports: list[dict[str, Any]]) -> None:
        all_reports = self.system_settings.setdefault("walk_forward_reports", [])
        all_reports[:] = [item for item in all_reports if item.get("run_id") != run_id]
        all_reports.extend({"run_id": run_id, **report} for report in reports)

    def list_backtest_runs(self, limit: int = 50) -> dict[str, Any]:
        items = [self._public_backtest_run(item) for item in self.backtest_runs]
        items.sort(key=lambda item: item.get("started_at") or "", reverse=True)
        return {"items": items[:limit], "total": len(items)}

    def latest_backtest_summary(self) -> dict[str, Any]:
        completed = [item for item in self.backtest_runs if item.get("status") == "COMPLETED"]
        if not completed:
            return {
                "status": "NO_BACKTEST_RUN",
                "message": "No backtest has been executed yet.",
                "next_action": "Run a backtest from the dashboard or call POST /api/backtests/run.",
            }
        completed.sort(key=lambda item: item.get("completed_at") or item.get("started_at") or "", reverse=True)
        return self._public_backtest_run(completed[0], include_summary=True)

    def get_backtest_run(self, run_id: str) -> dict[str, Any] | None:
        record = next((item for item in self.backtest_runs if str(item.get("run_id")) == str(run_id)), None)
        return self._public_backtest_run(record, include_summary=True) if record else None

    def get_backtest_trades(self, run_id: str, limit: int = 250) -> dict[str, Any]:
        rows = [item for item in self.backtest_trades if str(item.get("run_id")) == str(run_id)]
        return {"items": rows[:limit], "total": len(rows)}

    def get_walk_forward_folds(self, run_id: str) -> dict[str, Any]:
        rows = [item for item in self.system_settings.get("walk_forward_folds", []) if str(item.get("run_id")) == str(run_id)]
        return {"items": rows, "total": len(rows)}

    def save_setting(
        self,
        key: str,
        value: dict[str, Any],
        setting_group: str = "general",
        updated_by: str = "api",
        source: str = "dashboard",
    ) -> dict[str, Any]:
        now = datetime.now(tz=UTC).isoformat()
        record = {
            "setting_key": key,
            "setting_value": value,
            "setting_value_json": value,
            "setting_group": setting_group,
            "updated_by": updated_by,
            "source": source,
            "updated_at": now,
            "created_at": now,
        }
        self.system_settings[key] = record
        return record

    def get_setting(self, key: str) -> dict[str, Any] | None:
        value = self.system_settings.get(key)
        if isinstance(value, dict) and "setting_value_json" in value:
            return value
        if isinstance(value, dict):
            return {
                "setting_key": key,
                "setting_value": value,
                "setting_value_json": value,
                "setting_group": "legacy",
                "source": "memory",
                "updated_at": None,
            }
        return None

    def list_settings(self) -> dict[str, Any]:
        rows = [value for value in self.system_settings.values() if isinstance(value, dict) and "setting_key" in value]
        return {"items": rows, "total": len(rows)}

    def save_optimization_profile(self, profile: dict[str, Any], source_run_id: str | None = None, change_reason: str = "profile_saved") -> dict[str, Any]:
        profiles = self.system_settings.setdefault("optimization_profiles", [])
        profile_id = int(profile.get("id") or profile.get("profile_id") or len(profiles) + 1)
        payload = {
            "id": profile_id,
            "profile_id": profile_id,
            "name": profile.get("name", f"profile_{profile_id}"),
            "instrument": profile.get("instrument", "XAUUSD"),
            "timeframe": profile.get("timeframe", "5m"),
            "parameters": profile.get("parameters") or profile.get("parameters_json") or {},
            "is_active": bool(profile.get("is_active", False)),
            "source_run_id": source_run_id,
            "created_at": profile.get("created_at") or datetime.now(tz=UTC).isoformat(),
            "activated_at": profile.get("activated_at"),
        }
        if payload["is_active"]:
            for item in profiles:
                item["is_active"] = False
        profiles[:] = [item for item in profiles if int(item.get("profile_id", item.get("id", 0))) != profile_id]
        profiles.append(payload)
        versions = self.system_settings.setdefault("optimization_profile_versions", [])
        version_number = 1 + max([int(item.get("version_number", 0)) for item in versions if int(item.get("profile_id", 0)) == profile_id] or [0])
        versions.append(
            {
                "profile_id": profile_id,
                "version_number": version_number,
                "parameters": payload["parameters"],
                "change_reason": change_reason,
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
        )
        return payload

    def list_optimization_profiles(self) -> dict[str, Any]:
        profiles = list(self.system_settings.get("optimization_profiles", []))
        profiles.sort(key=lambda item: int(item.get("profile_id", item.get("id", 0))))
        return {"items": profiles, "total": len(profiles)}

    def get_active_optimization_profile(self) -> dict[str, Any] | None:
        profiles = self.list_optimization_profiles()["items"]
        return next((item for item in profiles if item.get("is_active")), profiles[0] if profiles else None)

    def set_active_optimization_profile(self, profile_id: int, reason: str = "activated") -> dict[str, Any] | None:
        profiles = self.system_settings.setdefault("optimization_profiles", [])
        active = None
        now = datetime.now(tz=UTC).isoformat()
        for profile in profiles:
            profile["is_active"] = int(profile.get("profile_id", profile.get("id", 0))) == profile_id
            if profile["is_active"]:
                profile["activated_at"] = now
                active = profile
        if active:
            self.save_optimization_profile(active, source_run_id=active.get("source_run_id"), change_reason=reason)
        return active

    def save_optimization_run(self, run: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        runs = self.system_settings.setdefault("optimization_runs", [])
        run_id = str(run.get("run_id") or run.get("id"))
        payload = {**run, "run_id": run_id}
        runs[:] = [item for item in runs if str(item.get("run_id")) != run_id and str(item.get("id")) != run_id]
        runs.append(payload)
        self.system_settings.setdefault("optimization_candidates", {})[run_id] = list(candidates)
        return payload

    def list_optimization_runs(self) -> dict[str, Any]:
        runs = list(self.system_settings.get("optimization_runs", []))
        runs.sort(key=lambda item: item.get("completed_at") or item.get("started_at") or "", reverse=True)
        return {"items": runs, "total": len(runs)}

    def get_optimization_run(self, run_id: int | str) -> dict[str, Any] | None:
        return next((item for item in self.system_settings.get("optimization_runs", []) if str(item.get("id")) == str(run_id) or str(item.get("run_id")) == str(run_id)), None)

    def get_optimization_candidates(self, run_id: int | str) -> dict[str, Any]:
        candidates = self.system_settings.get("optimization_candidates", {})
        items = candidates.get(str(run_id), [])
        if not items:
            run = self.get_optimization_run(run_id) or {}
            items = candidates.get(str(run.get("run_id")), [])
        return {"items": items, "total": len(items)}

    def save_optimization_rollback(self, from_profile_id: int | None, to_profile_id: int, reason: str = "rollback") -> None:
        self.system_settings.setdefault("optimization_rollbacks", []).append(
            {
                "from_profile_id": from_profile_id,
                "to_profile_id": to_profile_id,
                "reason": reason,
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
        )

    def save_model_weight_state(
        self,
        weights: dict[str, float],
        history: list[dict[str, Any]] | None = None,
        profile_versions: list[dict[str, Any]] | None = None,
        reason: str = "updated",
    ) -> dict[str, Any]:
        profile_id = "active"
        now = datetime.now(tz=UTC).isoformat()
        record = {
            "profile_id": profile_id,
            "name": "active",
            "is_active": True,
            "weights": weights,
            "weights_json": weights,
            "reason": reason,
            "updated_at": now,
        }
        self.system_settings["model_weight_profile.active"] = record
        if history:
            self.system_settings.setdefault("model_weight_history", []).extend(history)
        if profile_versions:
            self.system_settings.setdefault("model_weight_versions", []).extend(profile_versions)
        return record

    def load_model_weight_state(self) -> dict[str, Any]:
        profile = self.system_settings.get("model_weight_profile.active")
        return profile if isinstance(profile, dict) else {}

    def save_health_event(self, component: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "event_id": f"HEALTH-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S%f')}",
            "severity": status if status in {"INFO", "WARNING", "CRITICAL"} else ("CRITICAL" if status == "FAILED" else status),
            "component": component,
            "status": status,
            "message": message,
            "details": details or {},
            "created_at": datetime.now(tz=UTC).isoformat(),
        }
        self.system_settings.setdefault("health_events", []).append(event)
        return event

    def save_health_snapshot(self, component: str, status: str, details: dict[str, Any] | None = None, latency_ms: float | None = None, failure_count: int | None = None) -> dict[str, Any]:
        snapshot = {
            "component": component,
            "status": status,
            "latency_ms": latency_ms,
            "failure_count": failure_count,
            "details": details or {},
            "created_at": datetime.now(tz=UTC).isoformat(),
        }
        self.system_settings.setdefault("health_snapshots", []).append(snapshot)
        return snapshot

    def get_health_events(self, limit: int = 100) -> dict[str, Any]:
        rows = list(self.system_settings.get("health_events", []))
        return {"items": list(reversed(rows[-limit:])), "total": len(rows)}

    def get_latest_health_snapshot(self) -> dict[str, Any] | None:
        rows = self.system_settings.get("health_snapshots", [])
        return rows[-1] if rows else None

    def save_latest_market_state(self, state: dict[str, Any]) -> dict[str, Any]:
        # Live websocket price is intentionally process-local. It is useful for
        # execution checks, but stale prices must not survive an API restart.
        payload = {**state, "updated_at": datetime.now(tz=UTC).isoformat()}
        self.system_settings[f"latest_market_state.{state.get('instrument', 'XAUUSD')}"] = payload
        return payload

    def get_latest_market_state(self, instrument: str) -> dict[str, Any] | None:
        state = self.system_settings.get(f"latest_market_state.{instrument}")
        return state if isinstance(state, dict) else None

    def mark_interrupted_backtest_jobs(self) -> int:
        count = 0
        for run in self.backtest_runs:
            if run.get("status") == "RUNNING":
                run["status"] = "INTERRUPTED"
                run["error_message"] = "The previous run was interrupted by API restart."
                run["updated_at"] = datetime.now(tz=UTC).isoformat()
                count += 1
        for run in self.system_settings.get("walk_forward_runs", []):
            if run.get("status") == "RUNNING":
                run["status"] = "INTERRUPTED"
                run["error_message"] = "The previous run was interrupted by API restart."
                count += 1
        return count

    def import_backtest_reports(self, reports_dir: str | Path) -> dict[str, int]:
        base = Path(reports_dir)
        imported = {"backtests": 0, "walk_forward": 0, "loaded_from_db": len(self.backtest_runs)}
        imported["backtests"] += self._import_report_folder(base / "backtests", "BACKTEST")
        imported["walk_forward"] += self._import_report_folder(base / "walk_forward", "WALK_FORWARD")
        return imported

    def _import_report_folder(self, folder: Path, run_type: str) -> int:
        if not folder.exists():
            return 0
        imported = 0
        for summary_path in folder.glob("*/summary.json"):
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            run_id = str(summary.get("run_id") or summary.get("id") or summary_path.parent.name)
            if run_type == "WALK_FORWARD" and not run_id.startswith(("WF-", "WALK", "LEGACY")):
                run_id = f"WF-REPORT-{run_id}"
            if self.get_backtest_run(run_id):
                continue
            config = summary.get("config") or summary.get("config_json") or {}
            started_at = _parse_dt(summary.get("started_at") or summary.get("run_time")) or datetime.now(tz=UTC)
            completed_at = _parse_dt(summary.get("completed_at")) or started_at
            normalized_summary = summary.get("summary") if isinstance(summary.get("summary"), dict) else summary
            self.create_backtest_run(
                run_id=run_id,
                run_type=run_type,
                instrument=str(summary.get("instrument") or config.get("instrument") or "XAUUSD"),
                timeframe=str(summary.get("timeframe") or config.get("timeframe") or "1m"),
                config_json=config,
                status=str(summary.get("status") or "COMPLETED"),
                started_at=started_at,
            )
            self.update_backtest_run(
                run_id=run_id,
                status=str(summary.get("status") or "COMPLETED"),
                summary_json=normalized_summary,
                report_path=str(summary_path),
                completed_at=completed_at,
            )
            imported += 1
        return imported

    def _normalize_backtest_trade(self, run_id: str, trade: dict[str, Any], idx: int) -> dict[str, Any]:
        signal_time = trade.get("signal_time") or trade.get("time") or trade.get("trade_time")
        return {
            "id": idx,
            "run_id": run_id,
            "signal_time": signal_time,
            "signal_direction": trade.get("signal_direction") or trade.get("signal"),
            "entry_price": trade.get("entry_price") or trade.get("entry"),
            "stop_loss": trade.get("stop_loss"),
            "take_profit_1": trade.get("take_profit_1") or trade.get("tp1"),
            "take_profit_2": trade.get("take_profit_2") or trade.get("tp2"),
            "take_profit_3": trade.get("take_profit_3") or trade.get("tp3"),
            "exit_price": trade.get("exit_price"),
            "outcome": trade.get("outcome"),
            "pnl": trade.get("pnl") if trade.get("pnl") is not None else trade.get("realized_rr"),
            "risk_reward": trade.get("risk_reward"),
            "confidence": trade.get("confidence"),
            "score": trade.get("score"),
            "entry_time": trade.get("entry_time"),
            "exit_time": trade.get("exit_time"),
            "reason_json": trade.get("reason_json") or trade,
            "created_at": datetime.now(tz=UTC).isoformat(),
        }

    def _public_backtest_run(self, record: dict[str, Any], include_summary: bool = False) -> dict[str, Any]:
        summary = record.get("summary_json") or record.get("summary") or {}
        config = record.get("config_json") or record.get("config") or {}
        item = {
            "run_id": record.get("run_id"),
            "run_type": record.get("run_type"),
            "instrument": record.get("instrument"),
            "timeframe": record.get("timeframe"),
            "status": record.get("status"),
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
            "profit_factor": summary.get("profit_factor"),
            "win_rate": summary.get("win_rate"),
            "max_drawdown": summary.get("max_drawdown"),
            "number_of_trades": summary.get("number_of_trades") or summary.get("trades") or summary.get("total_signals"),
            "average_rr": summary.get("average_rr"),
            "buy_precision": summary.get("buy_precision"),
            "sell_precision": summary.get("sell_precision"),
            "blocked_signals": summary.get("blocked_signals"),
            "model_mode": config.get("model_mode") or summary.get("model_mode"),
            "report_path": record.get("report_path"),
            "error_message": record.get("error_message"),
        }
        if include_summary:
            item["summary"] = summary
            item["config"] = config
        return item


class PostgreSQLStorage(InMemoryStorage):
    """PostgreSQL-backed persistence with in-memory mirrors for API convenience."""

    def __init__(self, dsn: str, schema: str | None = None) -> None:
        super().__init__()
        try:
            import psycopg
            from psycopg import sql
            from psycopg.rows import dict_row
        except Exception as exc:  # pragma: no cover - dependency issue path
            raise RuntimeError("psycopg is required for PostgreSQLStorage") from exc

        self._psycopg = psycopg
        self._sql = sql
        self._dsn = dsn
        self._schema = schema
        from psycopg.rows import dict_row as _dict_row
        self._dict_row = _dict_row
        self._conn = self._psycopg.connect(self._dsn, autocommit=True, row_factory=self._dict_row)
        self._configure_schema()

    def _configure_schema(self) -> None:
        if not self._schema:
            return
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self._schema):
            raise ValueError(f"Invalid PostgreSQL schema name: {self._schema}")
        with self._conn.cursor() as cur:
            identifier = self._sql.Identifier(self._schema)
            cur.execute(self._sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(identifier))
            cur.execute(self._sql.SQL("SET search_path TO {}, public").format(identifier))

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def _json(self, data: Any) -> str:
        return json.dumps(data, ensure_ascii=True, default=str)

    def _ensure_connection(self) -> None:
        """Re-establish the database connection if it has been closed or dropped."""
        try:
            # psycopg3: conn.closed is 0 when open, non-zero when closed
            if getattr(self._conn, "closed", False):
                raise self._psycopg.OperationalError("Connection is closed")
            # A lightweight probe to detect a silently-broken TCP connection
            self._conn.execute("SELECT 1")
        except Exception:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = self._psycopg.connect(self._dsn, autocommit=True, row_factory=self._dict_row)
            self._configure_schema()

    def _execute(self, sql: str, params: tuple[Any, ...]) -> Any:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
        except Exception:
            # Attempt a single reconnect then retry
            self._ensure_connection()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)

    def _execute_returning_one(self, sql: str, params: tuple[Any, ...]) -> Any:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        except Exception:
            self._ensure_connection()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def _fetchall(self, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
        except Exception:
            self._ensure_connection()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def _fetchone(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        except Exception:
            self._ensure_connection()
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()

    def _executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> None:
        if not params_list:
            return
        try:
            with self._conn.cursor() as cur:
                cur.executemany(sql, params_list)
        except Exception:
            self._ensure_connection()
            with self._conn.cursor() as cur:
                cur.executemany(sql, params_list)

    def save_candles(self, candles: list[Candle]) -> None:
        super().save_candles(candles)
        sql = """
            INSERT INTO market_candles (
                instrument, timeframe, candle_time, open, high, low, close, volume
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (instrument, timeframe, candle_time)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """
        params = [
            (
                c.instrument,
                c.timeframe,
                c.candle_time,
                c.open,
                c.high,
                c.low,
                c.close,
                c.volume,
            )
            for c in candles
        ]
        try:
            self._executemany(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_candles: {exc}"

    def save_indicator_snapshot(self, snapshot: IndicatorSnapshot) -> None:
        super().save_indicator_snapshot(snapshot)
        sql = """
            INSERT INTO indicator_snapshots (
                instrument, timeframe, snapshot_time, trend_bias, trend_score,
                momentum_bias, momentum_score, volatility_status, atr,
                nearest_support, nearest_resistance, structure_bias,
                session_name, news_status, raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            snapshot.instrument,
            snapshot.timeframe,
            snapshot.snapshot_time,
            snapshot.trend.bias,
            snapshot.trend.score,
            snapshot.momentum.bias,
            snapshot.momentum.score,
            snapshot.volatility_status,
            snapshot.atr,
            snapshot.nearest_support,
            snapshot.nearest_resistance,
            snapshot.structure_bias,
            snapshot.session_name,
            snapshot.news_status,
            self._json(snapshot.raw_json),
        )
        try:
            self._execute(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_indicator_snapshot: {exc}"

    def save_model_predictions(self, predictions: list[ModelPrediction]) -> None:
        super().save_model_predictions(predictions)
        sql = """
            INSERT INTO model_predictions (
                instrument, timeframe, prediction_time, model_name, model_version,
                signal, buy_probability, sell_probability, hold_probability,
                confidence, expected_return, expected_range, horizon_candles, raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                p.instrument,
                p.timeframe,
                p.prediction_time,
                p.model_name,
                p.model_version,
                p.signal.value,
                p.buy_probability,
                p.sell_probability,
                p.hold_probability,
                p.confidence,
                p.expected_return,
                p.expected_range,
                p.prediction_horizon_candles,
                self._json(p.model_dump(mode="json")),
            )
            for p in predictions
        ]
        try:
            self._executemany(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_model_predictions: {exc}"

    def save_ensemble_prediction(self, prediction: EnsemblePrediction) -> None:
        super().save_ensemble_prediction(prediction)
        sql = """
            INSERT INTO ensemble_predictions (
                instrument, timeframe, prediction_time, ensemble_signal,
                ensemble_confidence, buy_score, sell_score, hold_score,
                agreement_status, raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            prediction.instrument,
            prediction.timeframe,
            prediction.prediction_time,
            prediction.ensemble_signal.value,
            prediction.ensemble_confidence,
            prediction.buy_score,
            prediction.sell_score,
            prediction.hold_score,
            prediction.agreement_status.value,
            self._json(prediction.model_dump(mode="json")),
        )
        try:
            self._execute(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_ensemble_prediction: {exc}"

    def save_strategy_decision(self, decision: StrategyDecision) -> None:
        super().save_strategy_decision(decision)
        sql = """
            INSERT INTO strategy_decisions (
                instrument, timeframe, decision_time, signal, status,
                score, confidence, model_consensus, indicator_bias,
                reasons, blocked_reasons, raw_json
            ) VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            decision.instrument,
            decision.timeframe,
            decision.signal.value,
            decision.status.value,
            decision.score,
            decision.confidence,
            decision.model_consensus,
            decision.indicator_bias,
            self._json(decision.reasons),
            self._json(decision.blocked_reasons),
            self._json(decision.model_dump(mode="json")),
        )
        try:
            self._execute(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_strategy_decision: {exc}"

    def save_recommendation(self, recommendation: FinalRecommendation) -> int:
        rec_id = super().save_recommendation(recommendation)
        sql = """
            INSERT INTO trade_recommendations (
                instrument, timeframe, signal_time, signal, status,
                confidence, score, entry_type, entry_price, current_price,
                stop_loss, take_profit_1, take_profit_2, take_profit_3,
                risk_reward, valid_until, model_consensus, indicator_bias,
                risk_status, reasons, blocked_reasons, raw_json
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id
        """
        params = (
            recommendation.instrument,
            recommendation.timeframe,
            recommendation.signal_time,
            recommendation.signal.value,
            recommendation.status.value,
            recommendation.confidence,
            recommendation.score,
            recommendation.entry_type.value if recommendation.entry_type else None,
            recommendation.entry_price,
            recommendation.current_price,
            recommendation.stop_loss,
            recommendation.take_profit_1,
            recommendation.take_profit_2,
            recommendation.take_profit_3,
            recommendation.risk_reward,
            recommendation.expiry_time,
            recommendation.model_consensus,
            recommendation.indicator_bias,
            recommendation.risk_status,
            self._json(recommendation.reasons),
            self._json(recommendation.blocked_reasons),
            self._json(recommendation.model_dump(mode="json")),
        )
        try:
            row = self._execute_returning_one(sql, params)
            if row:
                rec_id = int(row["id"])
                self._last_recommendation_id = rec_id
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_recommendation: {exc}"

        return rec_id

    def save_signal_snapshot(self, snapshot: SignalSnapshot) -> None:
        super().save_signal_snapshot(snapshot)
        sql = """
            INSERT INTO signal_snapshots (
                signal_id, model_votes_json, model_weights_json, indicator_summary_json,
                market_structure_json, risk_filters_json, blocked_reasons_json,
                entry_plan_json, raw_recommendation_json, market_regime_json,
                multi_timeframe_summary_json, dynamic_weights_json, entry_plans_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (signal_id)
            DO UPDATE SET
                model_votes_json = EXCLUDED.model_votes_json,
                model_weights_json = EXCLUDED.model_weights_json,
                indicator_summary_json = EXCLUDED.indicator_summary_json,
                market_structure_json = EXCLUDED.market_structure_json,
                risk_filters_json = EXCLUDED.risk_filters_json,
                blocked_reasons_json = EXCLUDED.blocked_reasons_json,
                entry_plan_json = EXCLUDED.entry_plan_json,
                raw_recommendation_json = EXCLUDED.raw_recommendation_json,
                market_regime_json = EXCLUDED.market_regime_json,
                multi_timeframe_summary_json = EXCLUDED.multi_timeframe_summary_json,
                dynamic_weights_json = EXCLUDED.dynamic_weights_json,
                entry_plans_json = EXCLUDED.entry_plans_json,
                created_at = EXCLUDED.created_at
        """
        params = (
            snapshot.signal_id,
            self._json(snapshot.model_votes_json),
            self._json(snapshot.model_weights_json),
            self._json(snapshot.indicator_summary_json),
            self._json(snapshot.market_structure_json),
            self._json(snapshot.risk_filters_json),
            self._json(snapshot.blocked_reasons_json),
            self._json(snapshot.entry_plan_json),
            self._json(snapshot.raw_recommendation_json),
            self._json(snapshot.market_regime_json),
            self._json(snapshot.multi_timeframe_summary_json),
            self._json(snapshot.dynamic_weights_json),
            self._json(snapshot.entry_plans_json),
            snapshot.created_at,
        )
        try:
            self._execute(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_signal_snapshot: {exc}"

    def save_risk_check(self, risk_check: RiskCheck) -> None:
        super().save_risk_check(risk_check)
        latest_recommendation_id = self._last_recommendation_id or len(self.trade_recommendations)
        sql = """
            INSERT INTO risk_checks (
                recommendation_id, risk_status, spread, max_allowed_spread,
                risk_reward, news_status, volatility_status,
                daily_loss_percent, consecutive_losses,
                blocked_reasons, raw_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            latest_recommendation_id,
            risk_check.risk_status.value,
            risk_check.spread,
            risk_check.max_allowed_spread,
            risk_check.risk_reward,
            risk_check.news_status,
            risk_check.volatility_status,
            None,
            None,
            self._json(risk_check.blocked_reasons),
            self._json(risk_check.model_dump(mode="json")),
        )
        try:
            self._execute(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_risk_check: {exc}"

    def save_outcome(self, outcome: SignalOutcome) -> None:
        super().save_outcome(outcome)
        sql = """
            INSERT INTO signal_outcomes (
                recommendation_id, outcome, entry_triggered,
                hit_tp1, hit_tp2, hit_tp3, hit_sl,
                max_favorable_move, max_adverse_move, realized_rr,
                closed_at, raw_json, entry_triggered_at, entry_triggered_price,
                highest_price_after_signal, lowest_price_after_signal,
                exit_price, exit_reason, pnl_points, pnl_percent,
                validation_window_candles, ambiguous_candle
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        params = (
            outcome.recommendation_id,
            outcome.outcome,
            outcome.entry_triggered,
            outcome.hit_tp1,
            outcome.hit_tp2,
            outcome.hit_tp3,
            outcome.hit_sl,
            outcome.max_favorable_move,
            outcome.max_adverse_move,
            outcome.realized_rr,
            outcome.closed_at,
            self._json(outcome.raw_json),
            outcome.entry_triggered_at,
            outcome.entry_triggered_price,
            outcome.highest_price_after_signal,
            outcome.lowest_price_after_signal,
            outcome.exit_price,
            outcome.exit_reason,
            outcome.pnl_points,
            outcome.pnl_percent,
            outcome.validation_window_candles,
            outcome.ambiguous_candle,
        )
        try:
            self._execute(sql, params)
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_outcome: {exc}"

    def update_recommendation(self, recommendation_id: int, recommendation: FinalRecommendation) -> None:
        super().update_recommendation(recommendation_id, recommendation)
        sql = """
            UPDATE trade_recommendations
            SET raw_json = %s
            WHERE id = %s
        """
        try:
            self._execute(sql, (self._json(recommendation.model_dump(mode="json")), recommendation_id))
        except Exception as exc:
            self.system_settings["last_db_error"] = f"update_recommendation: {exc}"

    def list_recommendations_with_ids(self) -> list[tuple[int, FinalRecommendation]]:
        rows = self._fetchall(
            "SELECT id, raw_json FROM trade_recommendations ORDER BY id ASC",
            (),
        )
        results: list[tuple[int, FinalRecommendation]] = []
        for row in rows:
            payload = row.get("raw_json")
            if isinstance(payload, str):
                payload = json.loads(payload)
            if not isinstance(payload, dict):
                continue
            try:
                results.append((int(row["id"]), FinalRecommendation.model_validate(payload)))
            except Exception:
                continue
        return results

    def get_signal_outcomes(self, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        offset = (safe_page - 1) * safe_page_size
        count_row = self._fetchone("SELECT COUNT(*) AS total FROM signal_outcomes", ())
        total = int(count_row["total"]) if count_row else 0
        rows = self._fetchall(
            """
            SELECT recommendation_id, outcome, entry_triggered, hit_tp1, hit_tp2, hit_tp3,
                   hit_sl, max_favorable_move, max_adverse_move, realized_rr, closed_at, raw_json,
                   entry_triggered_at, entry_triggered_price, highest_price_after_signal,
                   lowest_price_after_signal, exit_price, exit_reason, pnl_points, pnl_percent,
                   validation_window_candles, ambiguous_candle
            FROM signal_outcomes
            ORDER BY closed_at DESC
            LIMIT %s OFFSET %s
            """,
            (safe_page_size, offset),
        )
        items: list[dict[str, Any]] = []
        for row in rows:
            raw_json = row.get("raw_json")
            if isinstance(raw_json, str):
                try:
                    raw_json = json.loads(raw_json)
                except Exception:
                    raw_json = {}
            items.append(
                {
                    "recommendation_id": row.get("recommendation_id"),
                    "outcome": row.get("outcome"),
                    "entry_triggered": row.get("entry_triggered"),
                    "hit_tp1": row.get("hit_tp1"),
                    "hit_tp2": row.get("hit_tp2"),
                    "hit_tp3": row.get("hit_tp3"),
                    "hit_sl": row.get("hit_sl"),
                    "max_favorable_move": row.get("max_favorable_move"),
                    "max_adverse_move": row.get("max_adverse_move"),
                    "realized_rr": row.get("realized_rr"),
                    "closed_at": row.get("closed_at").isoformat() if row.get("closed_at") else None,
                    "raw_json": raw_json if isinstance(raw_json, dict) else {},
                    "entry_triggered_at": row.get("entry_triggered_at").isoformat() if row.get("entry_triggered_at") else None,
                    "entry_triggered_price": row.get("entry_triggered_price"),
                    "highest_price_after_signal": row.get("highest_price_after_signal"),
                    "lowest_price_after_signal": row.get("lowest_price_after_signal"),
                    "exit_price": row.get("exit_price"),
                    "exit_reason": row.get("exit_reason"),
                    "pnl_points": row.get("pnl_points"),
                    "pnl_percent": row.get("pnl_percent"),
                    "validation_window_candles": row.get("validation_window_candles"),
                    "ambiguous_candle": row.get("ambiguous_candle"),
                }
            )
        return {"total": total, "page": safe_page, "page_size": safe_page_size, "items": items}

    def get_signal_outcome(self, signal_id: int) -> dict[str, Any] | None:
        rows = self.get_signal_outcomes(page=1, page_size=500).get("items", [])
        for row in rows:
            if int(row.get("recommendation_id") or 0) == signal_id:
                return row
        return None

    def latest_recommendation(self) -> FinalRecommendation | None:
        row = self._fetchone(
            "SELECT id, raw_json FROM trade_recommendations ORDER BY signal_time DESC LIMIT 1",
            (),
        )
        if not row:
            return None
        if row.get("id") is not None:
            self._last_recommendation_id = int(row["id"])
        raw = row.get("raw_json")
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not raw:
            return None
        try:
            return FinalRecommendation.model_validate(raw)
        except Exception:
            return None

    def latest_recommendation_id(self) -> int | None:
        if self._last_recommendation_id is not None:
            return self._last_recommendation_id
        row = self._fetchone(
            "SELECT id FROM trade_recommendations ORDER BY signal_time DESC LIMIT 1",
            (),
        )
        if row and row.get("id") is not None:
            self._last_recommendation_id = int(row["id"])
        return self._last_recommendation_id

    def latest_model_votes(self, timeframe: str | None = None) -> list[ModelPrediction]:
        if timeframe:
            ts_row = self._fetchone("SELECT MAX(prediction_time) AS ts FROM model_predictions WHERE timeframe = %s", (timeframe,))
        else:
            ts_row = self._fetchone("SELECT MAX(prediction_time) AS ts FROM model_predictions", ())
        ts = ts_row.get("ts") if ts_row else None
        if ts is None:
            return []

        rows = self._fetchall(
            "SELECT raw_json FROM model_predictions WHERE prediction_time = %s ORDER BY model_name ASC",
            (ts,),
        )
        results: list[ModelPrediction] = []
        for row in rows:
            raw = row.get("raw_json")
            if isinstance(raw, str):
                raw = json.loads(raw)
            if not raw:
                continue
            try:
                results.append(ModelPrediction.model_validate(raw))
            except Exception:
                continue
        return results

    def latest_indicator_snapshot(self, timeframe: str | None = None) -> IndicatorSnapshot | None:
        row = self._fetchone(
            """
            SELECT instrument, timeframe, snapshot_time,
                   trend_bias, trend_score, momentum_bias, momentum_score,
                   volatility_status, atr, nearest_support, nearest_resistance,
                   structure_bias, session_name, news_status, raw_json
            FROM indicator_snapshots
            ORDER BY snapshot_time DESC
            LIMIT 1
            """,
            (),
        )
        if not row:
            return None

        raw_json_value = row.get("raw_json")
        if isinstance(raw_json_value, str):
            raw_json_value = json.loads(raw_json_value)

        try:
            return IndicatorSnapshot.model_validate(
                {
                    "instrument": row.get("instrument"),
                    "timeframe": row.get("timeframe"),
                    "snapshot_time": row.get("snapshot_time"),
                    "trend": {
                        "bias": row.get("trend_bias") or "NEUTRAL",
                        "score": float(row.get("trend_score") or 0.0),
                    },
                    "momentum": {
                        "bias": row.get("momentum_bias") or "MIXED",
                        "score": float(row.get("momentum_score") or 0.0),
                    },
                    "volatility_status": row.get("volatility_status") or "UNKNOWN",
                    "atr": float(row.get("atr") or 0.0),
                    "nearest_support": row.get("nearest_support"),
                    "nearest_resistance": row.get("nearest_resistance"),
                    "structure_bias": row.get("structure_bias") or "NEUTRAL",
                    "session_name": row.get("session_name") or "UNKNOWN",
                    "news_status": row.get("news_status") or "UNKNOWN",
                    "raw_json": raw_json_value if isinstance(raw_json_value, dict) else {},
                }
            )
        except Exception:
            return None

    def latest_risk_check(self, timeframe: str | None = None) -> RiskCheck | None:
        row = self._fetchone(
            """
            SELECT risk_status, spread, max_allowed_spread, risk_reward,
                   news_status, volatility_status, blocked_reasons, raw_json
            FROM risk_checks
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (),
        )
        if not row:
            return None

        blocked = row.get("blocked_reasons")
        if isinstance(blocked, str):
            try:
                blocked = json.loads(blocked)
            except Exception:
                blocked = []
        if not isinstance(blocked, list):
            blocked = []

        try:
            return RiskCheck.model_validate(
                {
                    "risk_status": row.get("risk_status") or "BLOCKED",
                    "risk_reward": float(row.get("risk_reward") or 0.0),
                    "spread_status": "HIGH" if (row.get("spread") or 0.0) > (row.get("max_allowed_spread") or 0.0) else "ACCEPTABLE",
                    "spread": float(row.get("spread") or 0.0),
                    "max_allowed_spread": float(row.get("max_allowed_spread") or 0.0),
                    "news_status": row.get("news_status") or "UNKNOWN",
                    "volatility_status": row.get("volatility_status") or "UNKNOWN",
                    "position_size_status": "VALID",
                    "blocked_reasons": blocked,
                }
            )
        except Exception:
            return None

    def get_signal_history(
        self,
        status: str | None = None,
        signal: str | None = None,
        timeframe: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        outcome: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []

        if status:
            clauses.append("status = %s")
            params.append(status)
        if signal:
            clauses.append("signal = %s")
            params.append(signal)
        if timeframe:
            clauses.append("timeframe = %s")
            params.append(timeframe)
        if from_time:
            clauses.append("signal_time >= %s")
            params.append(from_time)
        if to_time:
            clauses.append("signal_time <= %s")
            params.append(to_time)
        if outcome:
            # Outcome is the validated lifecycle state stored on the recommendation payload.
            # Backed by the expression index idx_trade_recommendations_outcome (db/007).
            clauses.append("raw_json->>'outcome_status' = %s")
            params.append(outcome)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        count_row = self._fetchone(
            f"SELECT COUNT(*) AS total FROM trade_recommendations {where_sql}",
            tuple(params),
        )
        total = int(count_row["total"]) if count_row else 0

        safe_page = max(page, 1)
        # Cap page size so a crafted request can't force an unbounded scan/serialization.
        safe_page_size = min(max(page_size, 1), 200)
        offset = (safe_page - 1) * safe_page_size

        rows = self._fetchall(
            (
                "SELECT id, raw_json "
                f"FROM trade_recommendations {where_sql} "
                "ORDER BY signal_time DESC LIMIT %s OFFSET %s"
            ),
            tuple(params + [safe_page_size, offset]),
        )

        items: list[dict[str, Any]] = []
        for row in rows:
            payload = row.get("raw_json")
            if isinstance(payload, str):
                payload = json.loads(payload)
            if isinstance(payload, dict):
                payload.setdefault("id", row.get("id"))
                items.append(payload)

        return {
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
            "items": items,
        }

    def get_signal_detail(self, signal_id: int) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT id, raw_json FROM trade_recommendations WHERE id = %s LIMIT 1",
            (signal_id,),
        )
        if not row:
            return None

        payload = row.get("raw_json")
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return None

        payload.setdefault("id", row.get("id"))
        return payload

    def get_signal_snapshot(self, signal_id: int) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT signal_id, model_votes_json, model_weights_json, indicator_summary_json,
                   market_structure_json, risk_filters_json, blocked_reasons_json,
                   entry_plan_json, raw_recommendation_json, market_regime_json,
                   multi_timeframe_summary_json, dynamic_weights_json, entry_plans_json, created_at
            FROM signal_snapshots
            WHERE signal_id = %s
            LIMIT 1
            """,
            (signal_id,),
        )
        if not row:
            return None

        def parsed(value: Any, fallback: Any) -> Any:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return fallback
            return value if value is not None else fallback

        return {
            "signal_id": row.get("signal_id"),
            "model_votes_json": parsed(row.get("model_votes_json"), []),
            "model_weights_json": parsed(row.get("model_weights_json"), {}),
            "indicator_summary_json": parsed(row.get("indicator_summary_json"), {}),
            "market_structure_json": parsed(row.get("market_structure_json"), {}),
            "risk_filters_json": parsed(row.get("risk_filters_json"), {}),
            "blocked_reasons_json": parsed(row.get("blocked_reasons_json"), []),
            "entry_plan_json": parsed(row.get("entry_plan_json"), {}),
            "raw_recommendation_json": parsed(row.get("raw_recommendation_json"), {}),
            "market_regime_json": parsed(row.get("market_regime_json"), {}),
            "multi_timeframe_summary_json": parsed(row.get("multi_timeframe_summary_json"), {}),
            "dynamic_weights_json": parsed(row.get("dynamic_weights_json"), {}),
            "entry_plans_json": parsed(row.get("entry_plans_json"), []),
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        }

    def latest_timeframe_confirmation(self) -> dict[str, Any]:
        in_memory = super().latest_timeframe_confirmation()
        if in_memory.get("status") != "INSUFFICIENT_DATA":
            return in_memory
        row = self._fetchone(
            """
            SELECT multi_timeframe_summary_json
            FROM signal_snapshots
            WHERE multi_timeframe_summary_json IS NOT NULL
              AND multi_timeframe_summary_json <> '{}'::jsonb
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (),
        )
        if not row:
            return in_memory
        payload = row.get("multi_timeframe_summary_json")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        return payload if isinstance(payload, dict) and payload else in_memory

    def save_model_performance_snapshot(
        self,
        metrics: dict[str, dict[str, Any]],
        weights: dict[str, float],
        source: str,
        timeframe: str,
    ) -> None:
        super().save_model_performance_snapshot(metrics, weights, source, timeframe)

        now = datetime.now(tz=UTC)
        for model_name, item in metrics.items():
            sql = """
                INSERT INTO model_performance (
                    model_name, timeframe, period_start, period_end,
                    buy_precision, sell_precision, hold_accuracy,
                    win_rate, profit_factor, false_signal_rate,
                    average_return, drift_score
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
            """
            params = (
                model_name,
                timeframe,
                now,
                now,
                item.get("buy_precision", 0.0),
                item.get("sell_precision", 0.0),
                item.get("hold_accuracy", 0.0),
                item.get("win_rate", 0.0),
                item.get("profit_factor", 0.0),
                item.get("false_signal_rate", 0.0),
                item.get("average_return", 0.0),
                item.get("drift_score", 0.0),
            )
            try:
                self._execute(sql, params)
            except Exception as exc:
                self.system_settings["last_db_error"] = f"save_model_performance_snapshot[{model_name}]: {exc}"

        try:
            self._execute(
                """
                    INSERT INTO system_settings (setting_key, setting_value)
                    VALUES (%s, %s)
                    ON CONFLICT (setting_key)
                    DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = now()
                """,
                ("dynamic_model_weights", self._json(weights)),
            )
        except Exception as exc:
            self.system_settings["last_db_error"] = f"save_dynamic_weights: {exc}"

    def create_backtest_run(
        self,
        run_id: str,
        run_type: str,
        instrument: str,
        timeframe: str,
        config_json: dict[str, Any],
        status: str = "RUNNING",
        started_at: datetime | None = None,
    ) -> dict[str, Any]:
        super().create_backtest_run(run_id, run_type, instrument, timeframe, config_json, status, started_at)
        started_at = started_at or datetime.now(tz=UTC)
        sql = """
            INSERT INTO backtest_runs (
                run_id, run_type, instrument, timeframe, status, started_at,
                settings_json, config_json, summary_json, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (run_id)
            DO UPDATE SET
                run_type = EXCLUDED.run_type,
                instrument = EXCLUDED.instrument,
                timeframe = EXCLUDED.timeframe,
                status = EXCLUDED.status,
                started_at = EXCLUDED.started_at,
                settings_json = EXCLUDED.settings_json,
                config_json = EXCLUDED.config_json,
                updated_at = now()
            RETURNING *
        """
        row = self._execute_returning_one(
            sql,
            (
                run_id,
                run_type,
                instrument,
                timeframe,
                status,
                started_at,
                self._json(config_json),
                self._json(config_json),
                self._json({}),
            ),
        )
        return self._row_to_backtest_record(row) if row else super().get_backtest_run(run_id) or {}

    def update_backtest_run(
        self,
        run_id: str,
        status: str,
        summary_json: dict[str, Any] | None = None,
        report_path: str | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> dict[str, Any]:
        super().update_backtest_run(run_id, status, summary_json, report_path, error_message, completed_at)
        completed_at = completed_at or (datetime.now(tz=UTC) if status in {"COMPLETED", "FAILED", "CANCELLED"} else None)
        sql = """
            UPDATE backtest_runs
            SET status = %s,
                summary_json = COALESCE(%s::jsonb, summary_json),
                report_path = COALESCE(%s, report_path),
                error_message = %s,
                completed_at = COALESCE(%s, completed_at),
                updated_at = now()
            WHERE run_id = %s
            RETURNING *
        """
        row = self._execute_returning_one(
            sql,
            (
                status,
                self._json(summary_json) if summary_json is not None else None,
                report_path,
                error_message,
                completed_at,
                run_id,
            ),
        )
        return self._row_to_backtest_record(row) if row else {}

    def save_backtest_trades(self, run_id: str, trades: list[dict[str, Any]]) -> None:
        super().save_backtest_trades(run_id, trades)
        self._execute("DELETE FROM backtest_trades WHERE run_id = %s", (run_id,))
        sql = """
            INSERT INTO backtest_trades (
                run_id, trade_time, signal_time, signal, signal_direction,
                status, entry_price, stop_loss, take_profit_1, take_profit_2,
                take_profit_3, exit_price, outcome, realized_rr, pnl,
                risk_reward, confidence, score, entry_time, exit_time,
                raw_json, reason_json
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
        """
        params: list[tuple[Any, ...]] = []
        for idx, trade in enumerate(trades, start=1):
            normalized = self._normalize_backtest_trade(run_id, trade, idx)
            signal_time = _parse_dt(normalized.get("signal_time")) or datetime.now(tz=UTC)
            params.append(
                (
                    run_id,
                    signal_time,
                    signal_time,
                    normalized.get("signal_direction"),
                    normalized.get("signal_direction"),
                    trade.get("status"),
                    normalized.get("entry_price"),
                    normalized.get("stop_loss"),
                    normalized.get("take_profit_1"),
                    normalized.get("take_profit_2"),
                    normalized.get("take_profit_3"),
                    normalized.get("exit_price"),
                    normalized.get("outcome"),
                    trade.get("realized_rr") or normalized.get("pnl"),
                    normalized.get("pnl"),
                    normalized.get("risk_reward"),
                    normalized.get("confidence"),
                    normalized.get("score"),
                    _parse_dt(normalized.get("entry_time")),
                    _parse_dt(normalized.get("exit_time")),
                    self._json(trade),
                    self._json(normalized.get("reason_json") or {}),
                )
            )
        self._executemany(sql, params)

    def save_backtest_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        super().save_backtest_metrics(run_id, metrics)
        self._execute("DELETE FROM backtest_metrics WHERE run_id = %s", (run_id,))
        params = []
        for key, value in metrics.items():
            metric_value = value if isinstance(value, (int, float)) else None
            params.append((run_id, str(key), metric_value, self._json({key: value})))
        self._executemany(
            """
            INSERT INTO backtest_metrics (run_id, metric_name, metric_value, metrics_json)
            VALUES (%s, %s, %s, %s)
            """,
            params,
        )

    def save_walk_forward_run(
        self,
        run_id: str,
        instrument: str,
        timeframe: str,
        status: str,
        config_json: dict[str, Any],
        summary_json: dict[str, Any],
        report_path: str | None,
        started_at: datetime | str | None = None,
        completed_at: datetime | str | None = None,
        error_message: str | None = None,
    ) -> None:
        super().save_walk_forward_run(
            run_id, instrument, timeframe, status, config_json, summary_json,
            report_path, started_at, completed_at, error_message,
        )
        self._execute(
            """
            INSERT INTO walk_forward_runs (
                run_id, backtest_run_id, instrument, timeframe, status,
                started_at, completed_at, config_json, summary_json,
                report_path, error_message, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (run_id)
            DO UPDATE SET
                instrument = EXCLUDED.instrument,
                timeframe = EXCLUDED.timeframe,
                status = EXCLUDED.status,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                config_json = EXCLUDED.config_json,
                summary_json = EXCLUDED.summary_json,
                report_path = EXCLUDED.report_path,
                error_message = EXCLUDED.error_message,
                updated_at = now()
            """,
            (
                run_id,
                run_id,
                instrument,
                timeframe,
                status,
                _parse_dt(started_at),
                _parse_dt(completed_at),
                self._json(config_json),
                self._json(summary_json),
                report_path,
                error_message,
            ),
        )

    def save_walk_forward_folds(self, run_id: str, folds: list[dict[str, Any]]) -> None:
        super().save_walk_forward_folds(run_id, folds)
        self._execute("DELETE FROM walk_forward_folds WHERE run_id = %s", (run_id,))
        params = []
        for idx, fold in enumerate(folds, start=1):
            summary = fold.get("summary") or fold.get("metrics_json") or {}
            params.append(
                (
                    run_id,
                    int(fold.get("window_id") or fold.get("fold_number") or idx),
                    _parse_dt(fold.get("train_start")),
                    _parse_dt(fold.get("train_end")),
                    _parse_dt(fold.get("test_start")),
                    _parse_dt(fold.get("test_end")),
                    fold.get("status", "COMPLETED"),
                    self._json(summary),
                    fold.get("report_path"),
                )
            )
        self._executemany(
            """
            INSERT INTO walk_forward_folds (
                run_id, fold_number, train_start, train_end, test_start,
                test_end, status, metrics_json, report_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            params,
        )

    def save_walk_forward_reports(self, run_id: str, reports: list[dict[str, Any]]) -> None:
        super().save_walk_forward_reports(run_id, reports)
        self._execute("DELETE FROM walk_forward_reports WHERE run_id = %s", (run_id,))
        params = [
            (
                run_id,
                report.get("report_type") or report.get("type") or "file",
                report.get("report_path") or report.get("path"),
                self._json(report.get("metadata_json") or report),
            )
            for report in reports
            if report.get("report_path") or report.get("path")
        ]
        self._executemany(
            """
            INSERT INTO walk_forward_reports (run_id, report_type, report_path, metadata_json)
            VALUES (%s, %s, %s, %s)
            """,
            params,
        )

    def list_backtest_runs(self, limit: int = 50) -> dict[str, Any]:
        rows = self._fetchall(
            """
            SELECT run_id, run_type, instrument, timeframe, status, started_at,
                   completed_at, config_json, summary_json, report_path, error_message,
                   created_at, updated_at
            FROM backtest_runs
            ORDER BY COALESCE(completed_at, started_at, created_at) DESC
            LIMIT %s
            """,
            (limit,),
        )
        count = self._fetchone("SELECT COUNT(*) AS total FROM backtest_runs", ())
        items = [self._public_backtest_run(self._row_to_backtest_record(row)) for row in rows]
        return {"items": items, "total": int(count["total"]) if count else len(items)}

    def latest_backtest_summary(self) -> dict[str, Any]:
        row = self._fetchone(
            """
            SELECT run_id, run_type, instrument, timeframe, status, started_at,
                   completed_at, config_json, summary_json, report_path, error_message,
                   created_at, updated_at
            FROM backtest_runs
            WHERE status = 'COMPLETED'
            ORDER BY COALESCE(completed_at, started_at, created_at) DESC
            LIMIT 1
            """,
            (),
        )
        if not row:
            return {
                "status": "NO_BACKTEST_RUN",
                "message": "No backtest has been executed yet.",
                "next_action": "Run a backtest from the dashboard or call POST /api/backtests/run.",
            }
        return self._public_backtest_run(self._row_to_backtest_record(row), include_summary=True)

    def get_backtest_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT run_id, run_type, instrument, timeframe, status, started_at,
                   completed_at, config_json, summary_json, report_path, error_message,
                   created_at, updated_at
            FROM backtest_runs
            WHERE run_id = %s
            LIMIT 1
            """,
            (run_id,),
        )
        return self._public_backtest_run(self._row_to_backtest_record(row), include_summary=True) if row else None

    def get_backtest_trades(self, run_id: str, limit: int = 250) -> dict[str, Any]:
        rows = self._fetchall(
            """
            SELECT run_id, signal_time, signal_direction, entry_price, stop_loss,
                   take_profit_1, take_profit_2, take_profit_3, exit_price,
                   outcome, pnl, risk_reward, confidence, score, entry_time,
                   exit_time, reason_json, created_at
            FROM backtest_trades
            WHERE run_id = %s
            ORDER BY signal_time ASC
            LIMIT %s
            """,
            (run_id, limit),
        )
        count = self._fetchone("SELECT COUNT(*) AS total FROM backtest_trades WHERE run_id = %s", (run_id,))
        return {"items": [self._coerce_row(row) for row in rows], "total": int(count["total"]) if count else len(rows)}

    def get_walk_forward_folds(self, run_id: str) -> dict[str, Any]:
        rows = self._fetchall(
            """
            SELECT run_id, fold_number, train_start, train_end, test_start, test_end,
                   status, metrics_json, report_path, created_at
            FROM walk_forward_folds
            WHERE run_id = %s
            ORDER BY fold_number ASC
            """,
            (run_id,),
        )
        return {"items": [self._coerce_row(row) for row in rows], "total": len(rows)}

    def import_backtest_reports(self, reports_dir: str | Path) -> dict[str, int]:
        count = self._fetchone("SELECT COUNT(*) AS total FROM backtest_runs", ())
        imported = super().import_backtest_reports(reports_dir)
        imported["loaded_from_db"] = int(count["total"]) if count else 0
        return imported

    def save_setting(
        self,
        key: str,
        value: dict[str, Any],
        setting_group: str = "general",
        updated_by: str = "api",
        source: str = "dashboard",
    ) -> dict[str, Any]:
        super().save_setting(key, value, setting_group, updated_by, source)
        row = self._execute_returning_one(
            """
            INSERT INTO system_settings (
                setting_key, setting_value, setting_value_json, setting_group,
                updated_by, source, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (setting_key)
            DO UPDATE SET
                setting_value = EXCLUDED.setting_value,
                setting_value_json = EXCLUDED.setting_value_json,
                setting_group = EXCLUDED.setting_group,
                updated_by = EXCLUDED.updated_by,
                source = EXCLUDED.source,
                updated_at = now()
            RETURNING setting_key, setting_value_json, setting_group, updated_by, source, created_at, updated_at
            """,
            (key, self._json(value), self._json(value), setting_group, updated_by, source),
        )
        return self._coerce_row(row) if row else super().get_setting(key) or {}

    def get_setting(self, key: str) -> dict[str, Any] | None:
        try:
            row = self._fetchone(
                """
                SELECT setting_key, setting_value_json, setting_value, setting_group,
                       updated_by, source, created_at, updated_at
                FROM system_settings
                WHERE setting_key = %s
                LIMIT 1
                """,
                (key,),
            )
        except Exception:
            row = self._fetchone(
                """
                SELECT setting_key, setting_value, updated_at
                FROM system_settings
                WHERE setting_key = %s
                LIMIT 1
                """,
                (key,),
            )
        return self._coerce_row(row) if row else None

    def list_settings(self) -> dict[str, Any]:
        try:
            rows = self._fetchall(
                """
                SELECT setting_key, setting_value_json, setting_value, setting_group,
                       updated_by, source, created_at, updated_at
                FROM system_settings
                ORDER BY setting_key ASC
                """,
                (),
            )
        except Exception:
            rows = self._fetchall(
                """
                SELECT setting_key, setting_value, updated_at
                FROM system_settings
                ORDER BY setting_key ASC
                """,
                (),
            )
        return {"items": [self._coerce_row(row) for row in rows], "total": len(rows)}

    def save_optimization_profile(self, profile: dict[str, Any], source_run_id: str | None = None, change_reason: str = "profile_saved") -> dict[str, Any]:
        payload = super().save_optimization_profile(profile, source_run_id, change_reason)
        profile_id = int(payload["profile_id"])
        row = self._execute_returning_one(
            """
            INSERT INTO optimization_profiles (
                profile_id, name, instrument, timeframe, is_active,
                parameters_json, source_run_id, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (profile_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                instrument = EXCLUDED.instrument,
                timeframe = EXCLUDED.timeframe,
                is_active = EXCLUDED.is_active,
                parameters_json = EXCLUDED.parameters_json,
                source_run_id = EXCLUDED.source_run_id,
                updated_at = now()
            RETURNING profile_id, name, instrument, timeframe, is_active, parameters_json, source_run_id, created_at, updated_at
            """,
            (
                profile_id,
                payload["name"],
                payload["instrument"],
                payload["timeframe"],
                payload["is_active"],
                self._json(payload["parameters"]),
                source_run_id,
            ),
        )
        version_row = self._fetchone(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS version FROM optimization_profile_versions WHERE profile_id = %s",
            (profile_id,),
        )
        self._execute(
            """
            INSERT INTO optimization_profile_versions (profile_id, version_number, parameters_json, change_reason)
            VALUES (%s, %s, %s, %s)
            """,
            (profile_id, int(version_row["version"]) if version_row else 1, self._json(payload["parameters"]), change_reason),
        )
        return self._optimization_profile_from_row(row) if row else payload

    def list_optimization_profiles(self) -> dict[str, Any]:
        rows = self._fetchall(
            """
            SELECT profile_id, name, instrument, timeframe, is_active, parameters_json,
                   source_run_id, created_at, updated_at
            FROM optimization_profiles
            ORDER BY profile_id ASC
            """,
            (),
        )
        return {"items": [self._optimization_profile_from_row(row) for row in rows], "total": len(rows)}

    def get_active_optimization_profile(self) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT profile_id, name, instrument, timeframe, is_active, parameters_json,
                   source_run_id, created_at, updated_at
            FROM optimization_profiles
            WHERE is_active = TRUE
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (),
        )
        if row:
            return self._optimization_profile_from_row(row)
        rows = self.list_optimization_profiles()["items"]
        return rows[0] if rows else None

    def set_active_optimization_profile(self, profile_id: int, reason: str = "activated") -> dict[str, Any] | None:
        current = self.get_active_optimization_profile()
        self._execute("UPDATE optimization_profiles SET is_active = FALSE, updated_at = now()", ())
        row = self._execute_returning_one(
            """
            UPDATE optimization_profiles
            SET is_active = TRUE, updated_at = now()
            WHERE profile_id = %s
            RETURNING profile_id, name, instrument, timeframe, is_active, parameters_json, source_run_id, created_at, updated_at
            """,
            (profile_id,),
        )
        if row:
            self.save_optimization_rollback(int(current["profile_id"]) if current else None, profile_id, reason)
            return self._optimization_profile_from_row(row)
        return None

    def save_optimization_run(self, run: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        super().save_optimization_run(run, candidates)
        run_id = str(run.get("run_id") or f"OPT-{run.get('id')}")
        numeric_id = int(run.get("id") or 0) or None
        row = self._execute_returning_one(
            """
            INSERT INTO optimization_runs (
                run_id, name, instrument, timeframe, search_space_json,
                started_at, completed_at, status, best_profile_id,
                summary_json, config_json, metrics_json, selected_profile_id,
                error_message, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (run_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                instrument = EXCLUDED.instrument,
                timeframe = EXCLUDED.timeframe,
                search_space_json = EXCLUDED.search_space_json,
                started_at = EXCLUDED.started_at,
                completed_at = EXCLUDED.completed_at,
                status = EXCLUDED.status,
                best_profile_id = EXCLUDED.best_profile_id,
                summary_json = EXCLUDED.summary_json,
                config_json = EXCLUDED.config_json,
                metrics_json = EXCLUDED.metrics_json,
                selected_profile_id = EXCLUDED.selected_profile_id,
                error_message = EXCLUDED.error_message,
                updated_at = now()
            RETURNING id, run_id, name, instrument, timeframe, search_space_json, started_at,
                      completed_at, status, best_profile_id, summary_json, config_json,
                      metrics_json, selected_profile_id, error_message
            """,
            (
                run_id,
                run.get("name"),
                run.get("instrument", "XAUUSD"),
                run.get("timeframe", "5m"),
                self._json(run.get("search_space") or run.get("config_json") or {}),
                _parse_dt(run.get("started_at")) or datetime.now(tz=UTC),
                _parse_dt(run.get("completed_at")),
                run.get("status", "COMPLETED"),
                run.get("best_profile_id"),
                self._json(run.get("summary") or {}),
                self._json(run.get("search_space") or {}),
                self._json(run.get("summary") or {}),
                run.get("best_profile_id"),
                run.get("error_message"),
            ),
        )
        db_run_id = int(row["id"]) if row else numeric_id
        self._execute("DELETE FROM optimization_candidates WHERE run_id = %s", (run_id,))
        params = []
        for candidate in candidates:
            params.append(
                (
                    db_run_id,
                    run_id,
                    int(candidate.get("id") or candidate.get("candidate_id") or 0),
                    candidate.get("profile_id"),
                    self._json(candidate.get("parameters") or {}),
                    self._json(candidate.get("training_score") or {}),
                    self._json(candidate.get("validation_score") or candidate.get("metrics") or {}),
                    self._json(candidate.get("unseen_test_score") or {}),
                    self._json(candidate.get("metrics") or candidate.get("validation_score") or {}),
                    candidate.get("score"),
                    candidate.get("rank"),
                    candidate.get("rejected_reason"),
                )
            )
        self._executemany(
            """
            INSERT INTO optimization_candidates (
                optimization_run_id, run_id, candidate_id, profile_id,
                parameters_json, train_metrics_json, validation_metrics_json,
                test_metrics_json, metrics_json, score, rank, rejected_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            params,
        )
        return self._optimization_run_from_row(row) if row else run

    def list_optimization_runs(self) -> dict[str, Any]:
        rows = self._fetchall(
            """
            SELECT id, run_id, name, instrument, timeframe, search_space_json, started_at,
                   completed_at, status, best_profile_id, summary_json, config_json,
                   metrics_json, selected_profile_id, error_message
            FROM optimization_runs
            ORDER BY COALESCE(completed_at, started_at, created_at) DESC
            """,
            (),
        )
        return {"items": [self._optimization_run_from_row(row) for row in rows], "total": len(rows)}

    def get_optimization_run(self, run_id: int | str) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT id, run_id, name, instrument, timeframe, search_space_json, started_at,
                   completed_at, status, best_profile_id, summary_json, config_json,
                   metrics_json, selected_profile_id, error_message
            FROM optimization_runs
            WHERE id::text = %s OR run_id = %s
            LIMIT 1
            """,
            (str(run_id), str(run_id)),
        )
        return self._optimization_run_from_row(row) if row else None

    def get_optimization_candidates(self, run_id: int | str) -> dict[str, Any]:
        run = self.get_optimization_run(run_id)
        durable_run_id = str(run.get("run_id") if run else run_id)
        rows = self._fetchall(
            """
            SELECT candidate_id, profile_id, parameters_json, train_metrics_json,
                   validation_metrics_json, test_metrics_json, metrics_json,
                   score, rank, rejected_reason, created_at
            FROM optimization_candidates
            WHERE run_id = %s
            ORDER BY rank ASC, candidate_id ASC
            """,
            (durable_run_id,),
        )
        return {"items": [self._optimization_candidate_from_row(row) for row in rows], "total": len(rows)}

    def save_optimization_rollback(self, from_profile_id: int | None, to_profile_id: int, reason: str = "rollback") -> None:
        super().save_optimization_rollback(from_profile_id, to_profile_id, reason)
        self._execute(
            """
            INSERT INTO optimization_rollbacks (from_profile_id, to_profile_id, reason)
            VALUES (%s, %s, %s)
            """,
            (from_profile_id, to_profile_id, reason),
        )

    def save_model_weight_state(
        self,
        weights: dict[str, float],
        history: list[dict[str, Any]] | None = None,
        profile_versions: list[dict[str, Any]] | None = None,
        reason: str = "updated",
    ) -> dict[str, Any]:
        record = super().save_model_weight_state(weights, history, profile_versions, reason)
        row = self._execute_returning_one(
            """
            INSERT INTO model_weight_profiles (
                profile_id, name, model_name, is_active, weights_json, created_at, updated_at
            ) VALUES (%s, %s, %s, TRUE, %s, now(), now())
            ON CONFLICT (profile_id) WHERE profile_id IS NOT NULL
            DO UPDATE SET weights_json = EXCLUDED.weights_json, is_active = TRUE, updated_at = now()
            RETURNING profile_id, name, is_active, weights_json, created_at, updated_at
            """,
            ("active", "active", "__profile__", self._json(weights)),
        )
        latest_version = self._fetchone(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS version FROM model_weight_versions WHERE profile_id = %s",
            ("active",),
        )
        self._execute(
            """
            INSERT INTO model_weight_versions (profile_id, version_number, weights_json, reason, metrics_snapshot_json)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("active", int(latest_version["version"]) if latest_version else 1, self._json(weights), reason, self._json({"history_count": len(history or [])})),
        )
        if history:
            params = []
            for item in history:
                params.append(
                    (
                        f"ADJ-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S%f')}-{item.get('model_name')}",
                        "active",
                        item.get("model_name"),
                        item.get("base_weight"),
                        item.get("effective_weight"),
                        json.dumps(item.get("adjustment_reason") or {}, ensure_ascii=True),
                        self._json(item),
                    )
                )
            self._executemany(
                """
                INSERT INTO model_weight_adjustments (
                    adjustment_id, profile_id, model_name, old_weight, new_weight,
                    reason, metrics_window_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                params,
            )
        return self._coerce_row(row) if row else record

    def load_model_weight_state(self) -> dict[str, Any]:
        try:
            profile = self._fetchone(
                """
                SELECT profile_id, name, is_active, weights_json, created_at, updated_at
                FROM model_weight_profiles
                WHERE profile_id = 'active' AND is_active = TRUE
                LIMIT 1
                """,
                (),
            )
        except Exception:
            return {}
        if not profile:
            return {}
        try:
            history = self._fetchall(
                """
                SELECT profile_id, version_number, weights_json, reason, metrics_snapshot_json, created_at
                FROM model_weight_versions
                WHERE profile_id = 'active'
                ORDER BY version_number ASC
                """,
                (),
            )
        except Exception:
            history = []
        payload = self._coerce_row(profile)
        payload["weights"] = payload.get("weights_json") or {}
        payload["versions"] = [self._coerce_row(row) for row in history]
        return payload

    def save_health_event(self, component: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        event = super().save_health_event(component, status, message, details)
        severity = event["severity"]
        if severity not in {"WARNING", "CRITICAL"}:
            return event
        self._execute(
            """
            INSERT INTO health_events (event_id, severity, component, message, details_json, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (event["event_id"], severity, component, message, self._json(details or {}), _parse_dt(event["created_at"])),
        )
        self._execute(
            """
            INSERT INTO system_health_events (component, status, message, details_json)
            VALUES (%s, %s, %s, %s)
            """,
            (component, status, message, self._json(details or {})),
        )
        return event

    def save_health_snapshot(self, component: str, status: str, details: dict[str, Any] | None = None, latency_ms: float | None = None, failure_count: int | None = None) -> dict[str, Any]:
        snapshot = super().save_health_snapshot(component, status, details, latency_ms, failure_count)
        self._execute(
            """
            INSERT INTO service_health_snapshots (
                component, status, latency_ms, failure_count, details_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (component, status, latency_ms, failure_count, self._json(details or {}), _parse_dt(snapshot["created_at"])),
        )
        self._execute("DELETE FROM service_health_snapshots WHERE created_at < now() - interval '30 days'", ())
        return snapshot

    def get_health_events(self, limit: int = 100) -> dict[str, Any]:
        rows = self._fetchall(
            """
            SELECT event_id, severity, component, message, details_json, created_at
            FROM health_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return {"items": [self._coerce_row(row) for row in rows], "total": len(rows)}

    def get_latest_health_snapshot(self) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT component, status, latency_ms, failure_count, details_json, created_at
            FROM service_health_snapshots
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (),
        )
        return self._coerce_row(row) if row else None

    def save_latest_market_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return super().save_latest_market_state(state)

    def get_latest_market_state(self, instrument: str) -> dict[str, Any] | None:
        return super().get_latest_market_state(instrument)

    def mark_interrupted_backtest_jobs(self) -> int:
        super_count = super().mark_interrupted_backtest_jobs()
        backtest_rows = self._execute_returning_one(
            """
            WITH updated AS (
                UPDATE backtest_runs
                SET status = 'INTERRUPTED',
                    error_message = 'The previous run was interrupted by API restart.',
                    updated_at = now()
                WHERE status = 'RUNNING'
                RETURNING 1
            )
            SELECT COUNT(*) AS total FROM updated
            """,
            (),
        )
        wf_rows = self._execute_returning_one(
            """
            WITH updated AS (
                UPDATE walk_forward_runs
                SET status = 'INTERRUPTED',
                    error_message = 'The previous run was interrupted by API restart.',
                    updated_at = now()
                WHERE status = 'RUNNING'
                RETURNING 1
            )
            SELECT COUNT(*) AS total FROM updated
            """,
            (),
        )
        return super_count + int(backtest_rows["total"] if backtest_rows else 0) + int(wf_rows["total"] if wf_rows else 0)

    def get_execution_order_by_signal(self, signal_id: int) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT id, signal_id, idempotency_key, instrument, epic, account_id,
                   account_name, environment, direction, size, order_type, status,
                   recommendation_status, entry_price, current_price, stop_loss,
                   take_profit_1, take_profit_2, take_profit_3, requested_at,
                   submitted_at, confirmed_at, deal_reference, deal_id,
                   transaction_id, outcome, outcome_reason, outcome_updated_at,
                   broker_status, rejection_reason, error_message, request_json,
                   response_json, confirm_json, created_at, updated_at
            FROM execution_orders
            WHERE signal_id = %s
            ORDER BY requested_at DESC
            LIMIT 1
            """,
            (signal_id,),
        )
        return self._coerce_row(row) if row else super().get_execution_order_by_signal(signal_id)

    def get_execution_order_by_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self._fetchone(
            """
            SELECT id, signal_id, idempotency_key, instrument, epic, account_id,
                   account_name, environment, direction, size, order_type, status,
                   recommendation_status, entry_price, current_price, stop_loss,
                   take_profit_1, take_profit_2, take_profit_3, requested_at,
                   submitted_at, confirmed_at, deal_reference, deal_id,
                   transaction_id, outcome, outcome_reason, outcome_updated_at,
                   broker_status, rejection_reason, error_message, request_json,
                   response_json, confirm_json, created_at, updated_at
            FROM execution_orders
            WHERE idempotency_key = %s
            LIMIT 1
            """,
            (idempotency_key,),
        )
        return self._coerce_row(row) if row else None

    def create_execution_order(self, order: dict[str, Any]) -> dict[str, Any]:
        payload = super().create_execution_order(order)
        row = self._execute_returning_one(
            """
            INSERT INTO execution_orders (
                signal_id, idempotency_key, instrument, epic, account_id,
                account_name, environment, direction, size, order_type, status,
                recommendation_status, entry_price, current_price, stop_loss,
                take_profit_1, take_profit_2, take_profit_3, requested_at,
                submitted_at, confirmed_at, deal_reference, deal_id, transaction_id,
                outcome, outcome_reason, outcome_updated_at, broker_status,
                rejection_reason, error_message, request_json, response_json,
                confirm_json, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, now(), now()
            )
            ON CONFLICT (idempotency_key)
            DO UPDATE SET
                status = EXCLUDED.status,
                account_id = COALESCE(EXCLUDED.account_id, execution_orders.account_id),
                account_name = COALESCE(EXCLUDED.account_name, execution_orders.account_name),
                size = EXCLUDED.size,
                submitted_at = COALESCE(EXCLUDED.submitted_at, execution_orders.submitted_at),
                confirmed_at = COALESCE(EXCLUDED.confirmed_at, execution_orders.confirmed_at),
                deal_reference = COALESCE(EXCLUDED.deal_reference, execution_orders.deal_reference),
                deal_id = COALESCE(EXCLUDED.deal_id, execution_orders.deal_id),
                transaction_id = COALESCE(EXCLUDED.transaction_id, execution_orders.transaction_id),
                outcome = COALESCE(EXCLUDED.outcome, execution_orders.outcome),
                outcome_reason = COALESCE(EXCLUDED.outcome_reason, execution_orders.outcome_reason),
                outcome_updated_at = COALESCE(EXCLUDED.outcome_updated_at, execution_orders.outcome_updated_at),
                broker_status = COALESCE(EXCLUDED.broker_status, execution_orders.broker_status),
                rejection_reason = COALESCE(EXCLUDED.rejection_reason, execution_orders.rejection_reason),
                error_message = COALESCE(EXCLUDED.error_message, execution_orders.error_message),
                request_json = EXCLUDED.request_json,
                response_json = EXCLUDED.response_json,
                confirm_json = EXCLUDED.confirm_json,
                updated_at = now()
            RETURNING id, signal_id, idempotency_key, instrument, epic, account_id,
                      account_name, environment, direction, size, order_type, status,
                      recommendation_status, entry_price, current_price, stop_loss,
                      take_profit_1, take_profit_2, take_profit_3, requested_at,
                      submitted_at, confirmed_at, deal_reference, deal_id,
                      transaction_id, outcome, outcome_reason, outcome_updated_at,
                      broker_status, rejection_reason, error_message, request_json,
                      response_json, confirm_json, created_at, updated_at
            """,
            (
                order.get("signal_id"),
                order.get("idempotency_key"),
                order.get("instrument"),
                order.get("epic"),
                order.get("account_id"),
                order.get("account_name"),
                order.get("environment", "demo"),
                order.get("direction"),
                order.get("size"),
                order.get("order_type", "MARKET"),
                order.get("status"),
                order.get("recommendation_status"),
                order.get("entry_price"),
                order.get("current_price"),
                order.get("stop_loss"),
                order.get("take_profit_1"),
                order.get("take_profit_2"),
                order.get("take_profit_3"),
                _parse_dt(order.get("requested_at")) or datetime.now(tz=UTC),
                _parse_dt(order.get("submitted_at")),
                _parse_dt(order.get("confirmed_at")),
                order.get("deal_reference"),
                order.get("deal_id"),
                order.get("transaction_id"),
                order.get("outcome", "PENDING"),
                order.get("outcome_reason"),
                _parse_dt(order.get("outcome_updated_at")),
                order.get("broker_status"),
                order.get("rejection_reason"),
                order.get("error_message"),
                self._json(order.get("request_json") or {}),
                self._json(order.get("response_json") or {}),
                self._json(order.get("confirm_json") or {}),
            ),
        )
        return self._coerce_row(row) if row else payload

    def update_execution_order(self, idempotency_key: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        super().update_execution_order(idempotency_key, updates)
        allowed = {
            "status", "account_id", "account_name", "size", "submitted_at",
            "confirmed_at", "deal_reference", "deal_id", "transaction_id",
            "outcome", "outcome_reason", "outcome_updated_at", "broker_status",
            "rejection_reason", "error_message", "request_json",
            "response_json", "confirm_json",
        }
        clean = {key: value for key, value in updates.items() if key in allowed}
        if not clean:
            return self.get_execution_order_by_idempotency_key(idempotency_key)
        assignments: list[str] = []
        params: list[Any] = []
        for key, value in clean.items():
            if key.endswith("_json"):
                value = self._json(value or {})
            elif key in {"submitted_at", "confirmed_at", "outcome_updated_at"}:
                value = _parse_dt(value)
            assignments.append(f"{key} = %s")
            params.append(value)
        params.append(idempotency_key)
        row = self._execute_returning_one(
            f"""
            UPDATE execution_orders
            SET {", ".join(assignments)}, updated_at = now()
            WHERE idempotency_key = %s
            RETURNING id, signal_id, idempotency_key, instrument, epic, account_id,
                      account_name, environment, direction, size, order_type, status,
                      recommendation_status, entry_price, current_price, stop_loss,
                      take_profit_1, take_profit_2, take_profit_3, requested_at,
                      submitted_at, confirmed_at, deal_reference, deal_id,
                      transaction_id, outcome, outcome_reason, outcome_updated_at,
                      broker_status, rejection_reason, error_message, request_json,
                      response_json, confirm_json, created_at, updated_at
            """,
            tuple(params),
        )
        return self._coerce_row(row) if row else None

    def list_execution_orders(
        self,
        limit: int = 100,
        page: int = 1,
        page_size: int | None = None,
        status: str | None = None,
        outcome: str | None = None,
        direction: str | None = None,
        market_session: str | None = None,
        from_time: datetime | str | None = None,
        to_time: datetime | str | None = None,
        signal_id: int | None = None,
        executed_only: bool = False,
    ) -> dict[str, Any]:
        safe_page = max(int(page or 1), 1)
        safe_page_size = max(int(page_size or limit or 100), 1)
        clauses: list[str] = []
        params: list[Any] = []
        if executed_only:
            clauses.append(
                "(execution_orders.status IN ('READY', 'SUBMITTED', 'CONFIRMED', 'REJECTED') "
                "OR execution_orders.deal_reference IS NOT NULL OR execution_orders.deal_id IS NOT NULL)"
            )
        if status:
            clauses.append("upper(execution_orders.status) = %s")
            params.append(status.upper())
        if outcome:
            clauses.append("upper(COALESCE(execution_orders.outcome, 'PENDING')) = %s")
            params.append(outcome.upper())
        if direction:
            clauses.append("upper(execution_orders.direction) = %s")
            params.append(direction.upper())
        session_filter = _normalized_session_filter(market_session)
        if session_filter == "UNKNOWN":
            clauses.append(
                """
                (
                    COALESCE(
                        NULLIF(request_json #>> '{recommendation,indicator_summary,session}', ''),
                        NULLIF(request_json #>> '{recommendation,indicator_summary,session_name}', ''),
                        NULLIF(request_json #>> '{recommendation,indicator_summary,market_session}', ''),
                        NULLIF(request_json #>> '{recommendation,indicator_summary,raw_json,session}', ''),
                        NULLIF(request_json #>> '{recommendation,indicator_summary,raw_json,session_name}', ''),
                        NULLIF(request_json #>> '{recommendation,indicator_summary,raw_json,market_session}', '')
                    ) IS NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM trade_recommendations tr
                        WHERE tr.id = execution_orders.signal_id
                          AND COALESCE(
                              NULLIF(tr.raw_json #>> '{indicator_summary,session}', ''),
                              NULLIF(tr.raw_json #>> '{indicator_summary,session_name}', ''),
                              NULLIF(tr.raw_json #>> '{indicator_summary,market_session}', ''),
                              NULLIF(tr.raw_json #>> '{indicator_summary,raw_json,session}', ''),
                              NULLIF(tr.raw_json #>> '{indicator_summary,raw_json,session_name}', ''),
                              NULLIF(tr.raw_json #>> '{indicator_summary,raw_json,market_session}', '')
                          ) IS NOT NULL
                    )
                )
                """
            )
        elif session_filter:
            candidates = tuple(alias.upper() for alias in _SESSION_FILTER_ALIASES.get(session_filter, (session_filter,)))
            clauses.append(
                """
                (
                    upper(COALESCE(request_json #>> '{recommendation,indicator_summary,session}', '')) = ANY(%s)
                    OR upper(COALESCE(request_json #>> '{recommendation,indicator_summary,session_name}', '')) = ANY(%s)
                    OR upper(COALESCE(request_json #>> '{recommendation,indicator_summary,market_session}', '')) = ANY(%s)
                    OR upper(COALESCE(request_json #>> '{recommendation,indicator_summary,raw_json,session}', '')) = ANY(%s)
                    OR upper(COALESCE(request_json #>> '{recommendation,indicator_summary,raw_json,session_name}', '')) = ANY(%s)
                    OR upper(COALESCE(request_json #>> '{recommendation,indicator_summary,raw_json,market_session}', '')) = ANY(%s)
                    OR EXISTS (
                        SELECT 1
                        FROM trade_recommendations tr
                        WHERE tr.id = execution_orders.signal_id
                          AND (
                              upper(COALESCE(tr.raw_json #>> '{indicator_summary,session}', '')) = ANY(%s)
                              OR upper(COALESCE(tr.raw_json #>> '{indicator_summary,session_name}', '')) = ANY(%s)
                              OR upper(COALESCE(tr.raw_json #>> '{indicator_summary,market_session}', '')) = ANY(%s)
                              OR upper(COALESCE(tr.raw_json #>> '{indicator_summary,raw_json,session}', '')) = ANY(%s)
                              OR upper(COALESCE(tr.raw_json #>> '{indicator_summary,raw_json,session_name}', '')) = ANY(%s)
                              OR upper(COALESCE(tr.raw_json #>> '{indicator_summary,raw_json,market_session}', '')) = ANY(%s)
                          )
                    )
                )
                """
            )
            params.extend([list(candidates)] * 12)
        parsed_from = _parse_dt(from_time)
        if parsed_from:
            clauses.append("execution_orders.requested_at >= %s")
            params.append(parsed_from)
        parsed_to = _parse_dt(to_time)
        if parsed_to:
            clauses.append("execution_orders.requested_at <= %s")
            params.append(parsed_to)
        if signal_id is not None:
            clauses.append("execution_orders.signal_id = %s")
            params.append(signal_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetchall(
            f"""
            SELECT execution_orders.id, execution_orders.signal_id, execution_orders.idempotency_key,
                   execution_orders.instrument, execution_orders.epic, execution_orders.account_id,
                   execution_orders.account_name, execution_orders.environment, execution_orders.direction,
                   execution_orders.size, execution_orders.order_type, execution_orders.status,
                   execution_orders.recommendation_status, execution_orders.entry_price,
                   execution_orders.current_price, execution_orders.stop_loss,
                   execution_orders.take_profit_1, execution_orders.take_profit_2,
                   execution_orders.take_profit_3, execution_orders.requested_at,
                   execution_orders.submitted_at, execution_orders.confirmed_at,
                   execution_orders.deal_reference, execution_orders.deal_id,
                   execution_orders.transaction_id, execution_orders.outcome,
                   execution_orders.outcome_reason, execution_orders.outcome_updated_at,
                   execution_orders.broker_status, execution_orders.rejection_reason,
                   execution_orders.error_message, execution_orders.request_json,
                   execution_orders.response_json, execution_orders.confirm_json,
                   execution_orders.created_at, execution_orders.updated_at,
                   COALESCE(
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,session}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,session_name}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,market_session}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,raw_json,session}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,raw_json,session_name}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,raw_json,market_session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,session_name}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,market_session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,raw_json,session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,raw_json,session_name}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,raw_json,market_session}}', '')
                   ) AS market_session_raw
            FROM execution_orders
            LEFT JOIN trade_recommendations tr ON tr.id = execution_orders.signal_id
            {where}
            ORDER BY requested_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [safe_page_size, (safe_page - 1) * safe_page_size]),
        )
        stats_rows = self._fetchall(
            f"""
            SELECT execution_orders.id, execution_orders.signal_id, execution_orders.direction,
                   execution_orders.status, execution_orders.outcome,
                   COALESCE(
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,session}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,session_name}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,market_session}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,raw_json,session}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,raw_json,session_name}}', ''),
                       NULLIF(execution_orders.request_json #>> '{{recommendation,indicator_summary,raw_json,market_session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,session_name}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,market_session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,raw_json,session}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,raw_json,session_name}}', ''),
                       NULLIF(tr.raw_json #>> '{{indicator_summary,raw_json,market_session}}', '')
                   ) AS market_session_raw
            FROM execution_orders
            LEFT JOIN trade_recommendations tr ON tr.id = execution_orders.signal_id
            {where}
            """,
            tuple(params),
        )
        count = self._fetchone(
            f"SELECT COUNT(*) AS total FROM execution_orders {where}",
            tuple(params),
        )
        items = [_annotate_execution_order_session(self._coerce_row(row)) for row in rows]
        statistics = _execution_order_statistics([self._coerce_row(row) for row in stats_rows])
        return {
            "items": items,
            "total": int(count["total"]) if count else len(rows),
            "page": safe_page,
            "page_size": safe_page_size,
            "statistics": statistics,
        }

    def save_execution_control_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        super().save_execution_control_decision(decision)
        row = self._execute_returning_one(
            """
            INSERT INTO execution_control_decisions (
                signal_id, source, source_kind, applied, allowed, reason,
                session_name, ensemble_signal, kronos_signal, kronos_relation,
                directional_vote_tie, buy_votes, sell_votes, hold_votes,
                config_json, decision_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            RETURNING id, signal_id, source, source_kind, applied, allowed, reason,
                      session_name, ensemble_signal, kronos_signal, kronos_relation,
                      directional_vote_tie, buy_votes, sell_votes, hold_votes,
                      config_json, decision_json, created_at
            """,
            (
                decision.get("signal_id"),
                decision.get("source"),
                decision.get("source_kind"),
                bool(decision.get("applied", True)),
                bool(decision.get("allowed", False)),
                decision.get("reason"),
                decision.get("session_name"),
                decision.get("ensemble_signal"),
                decision.get("kronos_signal"),
                decision.get("kronos_relation"),
                bool(decision.get("directional_vote_tie", False)),
                int(decision.get("buy_votes") or 0),
                int(decision.get("sell_votes") or 0),
                int(decision.get("hold_votes") or 0),
                self._json(decision.get("config") or {}),
                self._json(decision),
            ),
        )
        return self._coerce_row(row) if row else decision

    def list_execution_control_decisions(self, limit: int = 5000) -> dict[str, Any]:
        safe_limit = max(int(limit or 5000), 1)
        try:
            rows = self._fetchall(
                """
                SELECT id, signal_id, source, source_kind, applied, allowed, reason,
                       session_name, ensemble_signal, kronos_signal, kronos_relation,
                       directional_vote_tie, buy_votes, sell_votes, hold_votes,
                       config_json, decision_json, created_at
                FROM execution_control_decisions
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            count = self._fetchone("SELECT COUNT(*) AS total FROM execution_control_decisions", ())
            return {"items": [self._coerce_row(row) for row in rows], "total": int(count["total"]) if count else len(rows)}
        except Exception:
            return super().list_execution_control_decisions(limit=safe_limit)

    def save_execution_account_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = super().save_execution_account_snapshot(snapshot)
        row = self._execute_returning_one(
            """
            INSERT INTO execution_account_snapshots (
                account_id, account_name, environment, balance, available,
                profit_loss, raw_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            RETURNING account_id, account_name, environment, balance, available,
                      profit_loss, raw_json, created_at
            """,
            (
                snapshot.get("account_id"),
                snapshot.get("account_name"),
                snapshot.get("environment", "demo"),
                snapshot.get("balance"),
                snapshot.get("available"),
                snapshot.get("profit_loss"),
                self._json(snapshot.get("raw_json") or snapshot),
            ),
        )
        return self._coerce_row(row) if row else payload

    def latest_execution_account_snapshot(self, account_name: str | None = None) -> dict[str, Any] | None:
        if account_name:
            row = self._fetchone(
                """
                SELECT account_id, account_name, environment, balance, available,
                       profit_loss, raw_json, created_at
                FROM execution_account_snapshots
                WHERE account_name = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (account_name,),
            )
        else:
            row = self._fetchone(
                """
                SELECT account_id, account_name, environment, balance, available,
                       profit_loss, raw_json, created_at
                FROM execution_account_snapshots
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (),
            )
        return self._coerce_row(row) if row else super().latest_execution_account_snapshot(account_name)

    def _row_to_backtest_record(self, row: dict[str, Any] | None) -> dict[str, Any]:
        if not row:
            return {}
        return self._coerce_row(row)

    def _optimization_profile_from_row(self, row: dict[str, Any] | None) -> dict[str, Any]:
        data = self._coerce_row(row or {})
        params = data.get("parameters_json") or data.get("parameters") or {}
        return {
            "id": int(data.get("profile_id") or data.get("id") or 0),
            "profile_id": int(data.get("profile_id") or data.get("id") or 0),
            "name": data.get("name"),
            "instrument": data.get("instrument", "XAUUSD"),
            "timeframe": data.get("timeframe", "5m"),
            "parameters": params,
            "is_active": bool(data.get("is_active")),
            "source_run_id": data.get("source_run_id"),
            "created_at": data.get("created_at"),
            "activated_at": data.get("updated_at") if data.get("is_active") else None,
        }

    def _optimization_run_from_row(self, row: dict[str, Any] | None) -> dict[str, Any]:
        data = self._coerce_row(row or {})
        summary = data.get("summary_json") or data.get("metrics_json") or {}
        search_space = data.get("search_space_json") or data.get("config_json") or {}
        return {
            "id": int(data.get("id") or 0),
            "run_id": data.get("run_id") or f"OPT-{data.get('id')}",
            "name": data.get("name"),
            "instrument": data.get("instrument", "XAUUSD"),
            "timeframe": data.get("timeframe", "5m"),
            "search_space": search_space,
            "started_at": data.get("started_at"),
            "completed_at": data.get("completed_at"),
            "status": data.get("status"),
            "best_profile_id": data.get("best_profile_id") or data.get("selected_profile_id"),
            "summary": summary,
            "error_message": data.get("error_message"),
        }

    def _optimization_candidate_from_row(self, row: dict[str, Any] | None) -> dict[str, Any]:
        data = self._coerce_row(row or {})
        return {
            "id": data.get("candidate_id"),
            "candidate_id": data.get("candidate_id"),
            "profile_id": data.get("profile_id"),
            "parameters": data.get("parameters_json") or {},
            "metrics": data.get("metrics_json") or data.get("validation_metrics_json") or {},
            "training_score": data.get("train_metrics_json") or {},
            "validation_score": data.get("validation_metrics_json") or {},
            "unseen_test_score": data.get("test_metrics_json") or {},
            "score": data.get("score"),
            "rank": data.get("rank"),
            "rejected_reason": data.get("rejected_reason"),
            "created_at": data.get("created_at"),
        }

    def _coerce_row(self, row: dict[str, Any]) -> dict[str, Any]:
        coerced: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, datetime):
                coerced[key] = value.isoformat()
            elif hasattr(value, "__float__") and value.__class__.__module__ == "decimal":
                coerced[key] = float(value)
            elif isinstance(value, str) and key.endswith("_json"):
                try:
                    coerced[key] = json.loads(value)
                except Exception:
                    coerced[key] = value
            else:
                coerced[key] = value
        return coerced
