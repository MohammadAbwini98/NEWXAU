from __future__ import annotations

from datetime import timedelta
from typing import Optional

from .contracts import (
    EnsemblePrediction,
    FinalRecommendation,
    IndicatorSnapshot,
    RecommendationStatus,
    RiskCheck,
    StrategyDecision,
    TradePlan,
)


class RecommendationBuilder:
    """Builds final recommendation objects from all engines."""

    def build(
        self,
        strategy: StrategyDecision,
        snapshot: IndicatorSnapshot,
        ensemble: EnsemblePrediction,
        risk_check: Optional[RiskCheck],
        model_votes,
        trade_plan: Optional[TradePlan] = None,
    ) -> FinalRecommendation:
        status = strategy.status
        blocked_reasons = list(strategy.blocked_reasons)

        if risk_check is not None and risk_check.risk_status.value == "BLOCKED":
            blocked_reasons.extend(risk_check.blocked_reasons)
            status = self._risk_to_status(risk_check)

        reasons = list(strategy.reasons)
        if trade_plan is not None:
            reasons.append(trade_plan.reason)

        expiry_time = None
        if trade_plan is not None:
            expiry_time = snapshot.snapshot_time + timedelta(minutes=trade_plan.valid_for_minutes)

        return FinalRecommendation(
            instrument=snapshot.instrument,
            timeframe=snapshot.timeframe,
            signal_time=snapshot.snapshot_time,
            signal=strategy.signal,
            status=status,
            confidence=strategy.confidence,
            score=strategy.score,
            entry_type=trade_plan.entry_type if trade_plan else None,
            entry_price=trade_plan.entry_price if trade_plan else None,
            current_price=trade_plan.current_price if trade_plan else None,
            stop_loss=trade_plan.stop_loss if trade_plan else None,
            take_profit_1=trade_plan.take_profit_1 if trade_plan else None,
            take_profit_2=trade_plan.take_profit_2 if trade_plan else None,
            take_profit_3=trade_plan.take_profit_3 if trade_plan else None,
            risk_amount=trade_plan.risk if trade_plan else None,
            reward_amount=trade_plan.reward if trade_plan else None,
            risk_reward=trade_plan.risk_reward if trade_plan else None,
            risk_level=self._risk_level(trade_plan, risk_check),
            valid_for_minutes=trade_plan.valid_for_minutes if trade_plan else None,
            model_consensus=strategy.model_consensus,
            indicator_bias=strategy.indicator_bias,
            risk_status=(risk_check.risk_status.value if risk_check else strategy.risk_status),
            reasons=reasons,
            blocked_reasons=blocked_reasons,
            model_votes=list(model_votes),
            indicator_summary={
                "trend": snapshot.trend.model_dump(),
                "momentum": snapshot.momentum.model_dump(),
                "volatility_status": snapshot.volatility_status,
                "atr": snapshot.atr,
                "structure_bias": snapshot.structure_bias,
                "nearest_support": snapshot.nearest_support,
                "nearest_resistance": snapshot.nearest_resistance,
                "session": snapshot.session_name,
                "news_status": snapshot.news_status,
                "smc": snapshot.smc.model_dump() if snapshot.smc else None,
            },
            expiry_time=expiry_time,
            news_state_id=strategy.news_state_id,
            news_bias=strategy.news_bias,
            news_confidence=strategy.news_confidence,
            news_weight_used=strategy.news_weight_used,
            news_action_level=strategy.news_action_level,
            news_block_reason=strategy.news_block_reason,
            final_score_before_news=strategy.final_score_before_news,
            final_score_after_news=strategy.final_score_after_news,
        )

    def _risk_to_status(self, risk_check: RiskCheck) -> RecommendationStatus:
        text = " | ".join(risk_check.blocked_reasons).lower()
        if "spread" in text:
            return RecommendationStatus.BLOCKED_BY_SPREAD
        if "news" in text:
            return RecommendationStatus.BLOCKED_BY_NEWS
        if "risk/reward" in text:
            return RecommendationStatus.BLOCKED_BY_LOW_RR
        if "entry" in text:
            return RecommendationStatus.BLOCKED_BY_BAD_ENTRY
        if "structure" in text:
            return RecommendationStatus.BLOCKED_BY_MARKET_STRUCTURE
        if "conflict" in text:
            return RecommendationStatus.BLOCKED_BY_MODEL_CONFLICT
        return RecommendationStatus.BLOCKED_BY_RISK

    def _risk_level(self, trade_plan: Optional[TradePlan], risk_check: Optional[RiskCheck]) -> str:
        if trade_plan is None:
            return "NO_TRADE"
        if risk_check is not None and risk_check.risk_status.value == "BLOCKED":
            return "BLOCKED"
        if trade_plan.risk_reward < 1.5 or trade_plan.entry_quality_score < 55:
            return "HIGH"
        if trade_plan.risk_reward >= 2.0 and trade_plan.entry_quality_score >= 75:
            return "LOW"
        return "MEDIUM"
