from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from typing import Any

from .contracts import (
    EXECUTION_CONTROL_DIRECTIONS,
    EXECUTION_CONTROL_SESSIONS,
    ExecutionControlConfig,
    ExecutionControlDecision,
    FinalRecommendation,
    ModelPrediction,
    SignalDirection,
    normalize_execution_direction,
    normalize_execution_session_name,
)
from .market_sessions import gold_market_session_config, is_gold_session_trading_allowed, resolve_gold_market_session


SETTING_KEY = "execution_control.active"
DECISION_LIMIT = 5000


class ExecutionControlService:
    """Operator-configurable gates that run before Capital.com execution."""

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    def default_config(self) -> ExecutionControlConfig:
        return ExecutionControlConfig()

    def get_config(self) -> ExecutionControlConfig:
        record = self.storage.get_setting(SETTING_KEY) if hasattr(self.storage, "get_setting") else None
        raw = self._setting_value(record)
        if not raw:
            return self.default_config()
        try:
            return ExecutionControlConfig.model_validate(raw)
        except Exception:
            return self.default_config()

    def save_config(self, payload: dict[str, Any], updated_by: str = "dashboard") -> ExecutionControlConfig:
        current = self.get_config().model_dump(mode="json")
        incoming = dict(payload or {})
        merged = {**current, **incoming}
        if "allowed_sessions" in incoming:
            merged["allowed_sessions"] = {
                **current.get("allowed_sessions", {}),
                **dict(incoming.get("allowed_sessions") or {}),
            }
        if "allowed_directions" in incoming:
            merged["allowed_directions"] = {
                **current.get("allowed_directions", {}),
                **dict(incoming.get("allowed_directions") or {}),
            }
        config = ExecutionControlConfig.model_validate(merged)
        if hasattr(self.storage, "save_setting"):
            self.storage.save_setting(
                SETTING_KEY,
                config.model_dump(mode="json"),
                setting_group="execution_control",
                updated_by=updated_by,
                source="dashboard",
            )
        return config

    def evaluate(
        self,
        signal_id: int | None,
        recommendation: FinalRecommendation,
        source: str = "manual",
        record: bool = True,
    ) -> ExecutionControlDecision:
        config = self.get_config()
        session_name = self.session_from_recommendation(recommendation)
        direction = normalize_execution_direction(recommendation.signal.value)
        vote_context = self.kronos_vote_context(recommendation)
        source_kind = self.source_kind(source)
        config_payload = config.model_dump(mode="json")

        allowed = True
        applied = True
        reason = "Allowed by Control Unit."

        if not config.enabled:
            applied = False
            reason = "Control Unit is disabled."
        elif source_kind == "auto" and not config.apply_to_auto:
            applied = False
            reason = "Control Unit is not applied to automatic execution."
        elif source_kind == "manual" and not config.apply_to_manual:
            applied = False
            reason = "Control Unit is not applied to manual execution."
        elif session_name not in EXECUTION_CONTROL_SESSIONS:
            allowed = False
            reason = "Market session is unknown; Control Unit could not approve execution."
        elif not is_gold_session_trading_allowed(session_name):
            allowed = False
            reason = f"Market session {session_name} is a configured non-trading session."
        elif not bool(config.allowed_sessions.get(session_name, True)):
            allowed = False
            reason = f"Market session {session_name} is disabled by Control Unit."
        elif direction not in EXECUTION_CONTROL_DIRECTIONS:
            allowed = False
            reason = f"Trade direction {recommendation.signal.value} is not executable by Control Unit."
        elif not bool(config.allowed_directions.get(direction, True)):
            allowed = False
            reason = f"Trade direction {direction} is disabled by Control Unit."
        elif config.require_ensemble_opposite_or_tie and vote_context["kronos_relation"] not in {"OPPOSITE", "TIE"}:
            allowed = False
            reason = (
                "Control Unit requires ensemble to be opposite to Kronos or a directional vote tie; "
                f"current relation is {vote_context['kronos_relation']}."
            )

        decision = ExecutionControlDecision(
            signal_id=signal_id,
            source=source,
            source_kind=source_kind,
            applied=applied,
            allowed=allowed,
            reason=reason,
            session_name=session_name,
            ensemble_signal=vote_context["ensemble_signal"],
            kronos_signal=vote_context["kronos_signal"],
            kronos_relation=vote_context["kronos_relation"],
            directional_vote_tie=vote_context["directional_vote_tie"],
            buy_votes=vote_context["buy_votes"],
            sell_votes=vote_context["sell_votes"],
            hold_votes=vote_context["hold_votes"],
            config=config_payload,
            created_at=datetime.now(tz=UTC),
        )
        if record:
            self.record_decision(decision)
        return decision

    def record_decision(self, decision: ExecutionControlDecision) -> dict[str, Any] | None:
        if not hasattr(self.storage, "save_execution_control_decision"):
            return None
        try:
            return self.storage.save_execution_control_decision(decision.model_dump(mode="json"))
        except Exception:
            return None

    def statistics(self, what_if_limit: int = 200) -> dict[str, Any]:
        config = self.get_config()
        decisions = self._list_decisions()
        executions = self._execution_statistics()
        what_if = self._what_if_statistics(limit=what_if_limit)
        current_session = self.session_state_for_time(datetime.now(tz=UTC))
        return {
            "config": config.model_dump(mode="json"),
            "sessions": list(EXECUTION_CONTROL_SESSIONS),
            "session_config": gold_market_session_config(),
            "current_session": current_session["session"],
            "current_session_jordan_time": current_session["jordan_time"],
            "current_session_utc": current_session["utc"],
            "current_session_trading_allowed": current_session["trading_allowed"],
            "latest_decision": decisions[0] if decisions else None,
            "decision_summary": self._decision_summary(decisions),
            "execution_summary": executions,
            "what_if_current_config": what_if,
        }

    @staticmethod
    def source_kind(source: str) -> str:
        normalized = str(source or "").strip().lower()
        if "auto" in normalized or "background" in normalized or normalized == "manual_cycle":
            return "auto"
        return "manual"

    @staticmethod
    def session_for_time(value: datetime | None) -> str:
        return resolve_gold_market_session(value).session

    @staticmethod
    def session_state_for_time(value: datetime | None) -> dict[str, Any]:
        state = resolve_gold_market_session(value)
        return {
            "session": state.session,
            "utc": state.timestamp_utc.isoformat(),
            "jordan_time": state.jordan_time.isoformat(),
            "timezone": state.jordan_time.tzinfo.key if hasattr(state.jordan_time.tzinfo, "key") else "Asia/Amman",
            "trading_allowed": state.trading_allowed,
        }

    def session_from_recommendation(self, recommendation: FinalRecommendation) -> str:
        summary = recommendation.indicator_summary or {}
        candidates = [
            summary.get("session"),
            summary.get("session_name"),
            summary.get("market_session"),
            summary.get("raw_json", {}).get("session") if isinstance(summary.get("raw_json"), dict) else None,
        ]
        for candidate in candidates:
            session = normalize_execution_session_name(candidate)
            if session in EXECUTION_CONTROL_SESSIONS:
                return session
        return self.session_for_time(recommendation.signal_time)

    def kronos_vote_context(self, recommendation: FinalRecommendation) -> dict[str, Any]:
        votes = list(recommendation.model_votes or [])
        ensemble_signal = self._signal_value(recommendation.signal)
        kronos_signal: str | None = None
        buy_votes = sell_votes = hold_votes = 0

        for vote in votes:
            signal = self._signal_value(getattr(vote, "signal", None))
            if signal == "BUY":
                buy_votes += 1
            elif signal == "SELL":
                sell_votes += 1
            elif signal == "HOLD":
                hold_votes += 1
            model_name = str(getattr(vote, "model_name", "") or "").lower()
            if model_name == "kronos":
                kronos_signal = signal

        directional_vote_tie = buy_votes == sell_votes and buy_votes > 0
        if directional_vote_tie:
            relation = "TIE"
        elif not kronos_signal:
            relation = "MISSING_KRONOS"
        elif {ensemble_signal, kronos_signal} == {"BUY", "SELL"}:
            relation = "OPPOSITE"
        elif ensemble_signal == kronos_signal:
            relation = "SAME"
        elif kronos_signal == "HOLD" or ensemble_signal == "HOLD":
            relation = "NON_DIRECTIONAL"
        else:
            relation = "MIXED"

        return {
            "ensemble_signal": ensemble_signal,
            "kronos_signal": kronos_signal,
            "kronos_relation": relation,
            "directional_vote_tie": directional_vote_tie,
            "buy_votes": buy_votes,
            "sell_votes": sell_votes,
            "hold_votes": hold_votes,
        }

    def _list_decisions(self, limit: int = DECISION_LIMIT) -> list[dict[str, Any]]:
        if not hasattr(self.storage, "list_execution_control_decisions"):
            return []
        result = self.storage.list_execution_control_decisions(limit=limit)
        return list(result.get("items", []))

    def _decision_summary(self, decisions: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(decisions)
        allowed = sum(1 for item in decisions if bool(item.get("allowed")))
        blocked = total - allowed
        blocked_items = [item for item in decisions if not bool(item.get("allowed"))]
        return {
            "total": total,
            "allowed": allowed,
            "blocked": blocked,
            "by_session": self._count_by(decisions, "session_name"),
            "by_reason": self._count_by(decisions, "reason"),
            "by_block_reason": self._count_by(blocked_items, "reason"),
            "by_relation": self._count_by(decisions, "kronos_relation"),
            "by_source_kind": self._count_by(decisions, "source_kind"),
        }

    def _execution_statistics(self) -> dict[str, Any]:
        if not hasattr(self.storage, "list_execution_orders"):
            return {"total_orders": 0, "by_session": {}, "outcomes_by_session": {}, "outcomes_by_relation": {}}
        result = self.storage.list_execution_orders(limit=100000, page=1, page_size=100000, executed_only=False)
        orders = list(result.get("items", []))
        by_session: Counter[str] = Counter()
        by_relation: Counter[str] = Counter()
        outcomes_by_session: dict[str, Counter[str]] = {}
        outcomes_by_relation: dict[str, Counter[str]] = {}

        for order in orders:
            recommendation = self._recommendation_for_order(order)
            if recommendation is not None:
                session = self.session_from_recommendation(recommendation)
                relation = self.kronos_vote_context(recommendation)["kronos_relation"]
            else:
                session = "UNKNOWN"
                relation = "UNKNOWN"
            outcome = str(order.get("outcome") or "PENDING").upper()
            by_session[session] += 1
            by_relation[relation] += 1
            outcomes_by_session.setdefault(session, Counter())[outcome] += 1
            outcomes_by_relation.setdefault(relation, Counter())[outcome] += 1

        return {
            "total_orders": len(orders),
            "by_session": dict(by_session),
            "by_relation": dict(by_relation),
            "outcomes_by_session": {key: dict(value) for key, value in outcomes_by_session.items()},
            "outcomes_by_relation": {key: dict(value) for key, value in outcomes_by_relation.items()},
        }

    def _what_if_statistics(self, limit: int = 200) -> dict[str, Any]:
        if not hasattr(self.storage, "list_recommendations_with_ids"):
            return {"sample_size": 0, "allowed": 0, "blocked": 0, "by_reason": {}, "by_session": {}, "by_relation": {}}
        rows = list(self.storage.list_recommendations_with_ids())[-max(int(limit or 0), 1):]
        decisions: list[dict[str, Any]] = []
        for signal_id, recommendation in rows:
            rec = recommendation if isinstance(recommendation, FinalRecommendation) else self._recommendation_from_payload(recommendation)
            if rec is None:
                continue
            decisions.append(self.evaluate(int(signal_id), rec, source="what_if_auto", record=False).model_dump(mode="json"))
        summary = self._decision_summary(decisions)
        return {
            "sample_size": len(decisions),
            "allowed": summary["allowed"],
            "blocked": summary["blocked"],
            "by_reason": summary["by_reason"],
            "by_session": summary["by_session"],
            "by_relation": summary["by_relation"],
        }

    def _recommendation_for_order(self, order: dict[str, Any]) -> FinalRecommendation | None:
        signal_id = order.get("signal_id")
        if signal_id is not None and hasattr(self.storage, "get_signal_detail"):
            payload = self.storage.get_signal_detail(int(signal_id))
            recommendation = self._recommendation_from_payload(payload)
            if recommendation is not None:
                return recommendation
        request_json = order.get("request_json") if isinstance(order, dict) else None
        if isinstance(request_json, dict):
            return self._recommendation_from_payload(request_json.get("recommendation"))
        return None

    @staticmethod
    def _recommendation_from_payload(payload: Any) -> FinalRecommendation | None:
        if isinstance(payload, FinalRecommendation):
            return payload
        if isinstance(payload, dict):
            try:
                return FinalRecommendation.model_validate(payload)
            except Exception:
                return None
        return None

    @staticmethod
    def _setting_value(record: dict[str, Any] | None) -> dict[str, Any] | None:
        if not record:
            return None
        raw = record.get("setting_value_json", record.get("setting_value"))
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None
        return None

    @staticmethod
    def _signal_value(value: Any) -> str:
        if isinstance(value, SignalDirection):
            return value.value
        if isinstance(value, ModelPrediction):
            return value.signal.value
        return str(value or "").strip().upper()

    @staticmethod
    def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
        counts: Counter[str] = Counter(str(item.get(key) or "UNKNOWN") for item in items)
        return dict(counts)
