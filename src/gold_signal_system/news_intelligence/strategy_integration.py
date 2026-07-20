from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

from .models import ActionLevel, ImpactStrength, NewsDirection, StrategyNewsStateModel, TradeBias

logger = logging.getLogger(__name__)


class NewsStateAggregator:
    """Aggregate active news analyses into one strategy-readable state."""

    def __init__(self, repository: Any, config: Any = None) -> None:
        self.repository = repository
        self.config = config

    def aggregate(self, instrument: str) -> StrategyNewsStateModel:
        analyses = self.repository.get_ai_analyses(instrument, limit=100, active_only=True)
        active = [row for row in analyses if self._is_usable(row)]
        if not active:
            state = self._default_state(instrument, reason="No active high-relevance news.")
            self.repository.save_strategy_news_state(state)
            return state

        weighted_score_sum = 0.0
        total_weight = 0.0
        max_confidence = 0.0
        block_trading = False
        reduce_position_size = False
        highest_action = ActionLevel.INFO_ONLY
        reasons: list[str] = []
        event_types: list[str] = []
        valid_until_values: list[datetime] = []
        up_votes = 0
        down_votes = 0

        for row in active:
            direction = str(row.get("direction") or NewsDirection.UNKNOWN.value).upper()
            confidence = max(0.0, min(1.0, float(row.get("confidence") or 0.0)))
            impact = str(row.get("impact_strength") or ImpactStrength.LOW.value).upper()
            weight = max(0.0, min(float(row.get("news_weight") or 0.0), self._weight_cap(impact)))
            score = self._direction_to_score(direction) * confidence * self._impact_multiplier(impact)
            weighted_score_sum += score * weight
            total_weight += weight
            max_confidence = max(max_confidence, confidence)

            if direction == NewsDirection.UP.value:
                up_votes += 1
            elif direction == NewsDirection.DOWN.value:
                down_votes += 1

            action = self._action(str(row.get("action_level") or ActionLevel.INFO_ONLY.value))
            if self._action_priority(action) > self._action_priority(highest_action):
                highest_action = action
            block_trading = block_trading or bool(row.get("should_block_trading"))
            reduce_position_size = reduce_position_size or bool(row.get("should_reduce_position_size"))
            if action in {ActionLevel.RISK_REDUCE, ActionLevel.BLOCK_NEW_TRADES, ActionLevel.MANUAL_REVIEW}:
                reduce_position_size = True
            if action in {ActionLevel.BLOCK_NEW_TRADES, ActionLevel.MANUAL_REVIEW}:
                block_trading = True
            reasons.append(str(row.get("summary") or "").strip())
            event_types.append(str(row.get("event_type") or "UNKNOWN"))
            valid_until = self._parse_dt(row.get("valid_until"))
            if valid_until:
                valid_until_values.append(valid_until)

        aggregate_score = weighted_score_sum / total_weight if total_weight else 0.0
        direction = NewsDirection.NEUTRAL
        bias = TradeBias.HOLD
        if aggregate_score >= 0.30:
            direction = NewsDirection.UP
            bias = TradeBias.BUY
        elif aggregate_score <= -0.30:
            direction = NewsDirection.DOWN
            bias = TradeBias.SELL

        if up_votes and down_votes:
            direction = NewsDirection.MIXED
            bias = TradeBias.NO_TRADE
            reduce_position_size = True
            if highest_action in {ActionLevel.BLOCK_NEW_TRADES, ActionLevel.MANUAL_REVIEW}:
                block_trading = True
            reasons.insert(0, "Active news is directionally conflicting; risk is elevated.")

        state = StrategyNewsStateModel(
            instrument=instrument,
            active_direction=direction.value,
            active_trade_bias=bias.value,
            active_confidence=max_confidence,
            active_news_weight=min(total_weight, self._max_total_weight()),
            block_trading=block_trading,
            reduce_position_size=reduce_position_size,
            action_level=highest_action.value,
            reason="; ".join(reason for reason in reasons[:3] if reason) or "Active news state.",
            active_event_type=event_types[0] if event_types else "UNKNOWN",
            valid_until=max(valid_until_values) if valid_until_values else None,
            updated_at=datetime.now(tz=UTC),
        )
        state_id = self.repository.save_strategy_news_state(state)
        if state_id:
            state.id = state_id
        return state

    def shadow_adjust_decision(self, baseline_score: float, signal: str, state: StrategyNewsStateModel | None) -> dict[str, Any]:
        if state is None or state.active_news_weight <= 0:
            return {
                "baseline_expected_score": baseline_score,
                "news_adjusted_score": baseline_score,
                "baseline_action": signal,
                "news_adjusted_action": signal,
                "baseline_position_size": 1.0,
                "news_adjusted_position_size": 1.0,
            }
        adjusted = baseline_score
        if state.active_trade_bias == signal:
            adjusted += 15.0 * state.active_news_weight
        elif state.active_trade_bias in {"BUY", "SELL"} and signal in {"BUY", "SELL"}:
            adjusted -= 15.0 * state.active_news_weight
        multiplier = 0.0 if state.block_trading else (0.5 if state.reduce_position_size else 1.0)
        return {
            "baseline_expected_score": round(baseline_score, 2),
            "news_adjusted_score": round(adjusted, 2),
            "baseline_action": signal,
            "news_adjusted_action": "BLOCKED_BY_NEWS" if state.block_trading else signal,
            "baseline_position_size": 1.0,
            "news_adjusted_position_size": multiplier,
        }

    def _is_usable(self, row: dict[str, Any]) -> bool:
        valid_until = self._parse_dt(row.get("valid_until"))
        if valid_until is not None and valid_until <= datetime.now(tz=UTC):
            return False
        confidence = float(row.get("confidence") or 0.0)
        relevance = str(row.get("news_relevance") or "UNKNOWN").upper()
        min_conf = float(getattr(self.config, "news_min_ai_confidence", 0.65) if self.config else 0.65)
        return relevance in {"HIGH", "CRITICAL"} or confidence >= min_conf

    def _default_state(self, instrument: str, reason: str) -> StrategyNewsStateModel:
        return StrategyNewsStateModel(
            instrument=instrument,
            active_direction=NewsDirection.NEUTRAL.value,
            active_trade_bias=TradeBias.HOLD.value,
            active_confidence=0.0,
            active_news_weight=0.0,
            block_trading=False,
            reduce_position_size=False,
            action_level=ActionLevel.INFO_ONLY.value,
            reason=reason,
            active_event_type="UNKNOWN",
            valid_until=None,
            updated_at=datetime.now(tz=UTC),
        )

    @staticmethod
    def _direction_to_score(direction: str) -> float:
        return {NewsDirection.UP.value: 1.0, NewsDirection.DOWN.value: -1.0}.get(direction, 0.0)

    @staticmethod
    def _impact_multiplier(impact: str) -> float:
        return {
            ImpactStrength.LOW.value: 0.25,
            ImpactStrength.MEDIUM.value: 0.50,
            ImpactStrength.HIGH.value: 0.80,
            ImpactStrength.EXTREME.value: 1.00,
        }.get(impact, 0.50)

    def _weight_cap(self, impact: str) -> float:
        if impact in {ImpactStrength.HIGH.value, ImpactStrength.EXTREME.value}:
            return float(getattr(self.config, "news_max_weight_high_impact", 0.35) if self.config else 0.35)
        return float(getattr(self.config, "news_max_weight_normal", 0.20) if self.config else 0.20)

    def _max_total_weight(self) -> float:
        return float(getattr(self.config, "news_max_weight_high_impact", 0.35) if self.config else 0.35)

    @staticmethod
    def _action(value: str) -> ActionLevel:
        try:
            return ActionLevel(value)
        except Exception:
            return ActionLevel.INFO_ONLY

    @staticmethod
    def _action_priority(level: ActionLevel) -> int:
        return {
            ActionLevel.INFO_ONLY: 1,
            ActionLevel.WEIGHT_ONLY: 2,
            ActionLevel.RISK_REDUCE: 3,
            ActionLevel.BLOCK_NEW_TRADES: 4,
            ActionLevel.MANUAL_REVIEW: 5,
        }[level]

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
