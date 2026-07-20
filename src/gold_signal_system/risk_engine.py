from __future__ import annotations

from dataclasses import dataclass

from .config import RiskLimits
from .contracts import EnsemblePrediction, IndicatorSnapshot, MarketContext, RiskCheck, RiskStatus, TradePlan
from .news_intelligence.models import StrategyNewsStateModel


@dataclass(slots=True)
class PositionSizingInput:
    account_balance: float
    risk_percent: float
    stop_loss_distance_value: float
    value_per_point: float


class RiskEngine:
    """Phase 6: enforce hard safety rules and block unsafe signals."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def validate(
        self,
        trade_plan: TradePlan,
        snapshot: IndicatorSnapshot,
        ensemble: EnsemblePrediction,
        context: MarketContext,
        news_state: StrategyNewsStateModel | None = None,
    ) -> RiskCheck:
        blocked: list[str] = []

        spread_status = "ACCEPTABLE"
        if context.spread > self.limits.max_spread:
            spread_status = "HIGH"
            blocked.append("Spread is above max allowed.")
        elif context.spread > self.limits.max_spread * 0.8:
            spread_status = "ELEVATED"

        if trade_plan.risk_reward < self.limits.minimum_rr:
            blocked.append(f"Risk/reward is below {self.limits.minimum_rr:.1f}.")

        if context.minutes_to_high_impact_news is not None and context.minutes_to_high_impact_news <= self.limits.news_block_before_minutes:
            blocked.append("High-impact news window active before event.")

        if context.minutes_since_high_impact_news is not None and context.minutes_since_high_impact_news <= self.limits.news_block_after_minutes:
            blocked.append("High-impact news window active after event.")
            
        if news_state and news_state.block_trading:
            blocked.append(f"Trading blocked by AI News Intelligence: {news_state.reason}")

        if context.daily_loss_percent >= self.limits.max_daily_loss_pct:
            blocked.append("Daily loss limit reached.")

        if context.consecutive_losses >= self.limits.max_consecutive_losses:
            blocked.append("Max consecutive losses reached.")

        if context.open_recommendations >= self.limits.max_open_trades:
            blocked.append("Max open trades reached.")

        sl_distance = abs(trade_plan.entry_price - trade_plan.stop_loss)
        atr = max(snapshot.atr, 0.1)
        if sl_distance < atr * 0.30:
            blocked.append("SL distance too small.")
        if sl_distance > atr * 4.0:
            blocked.append("SL distance too large.")

        if ensemble.agreement_status.value == "HIGH_CONFLICT":
            blocked.append("Model conflict is high.")

        if snapshot.volatility_status == "TOO_LOW":
            blocked.append("ATR too low.")

        if snapshot.volatility_status == "EXTREME" and not context.special_volatility_mode:
            blocked.append("ATR extreme without special volatility mode.")

        if trade_plan.entry_type.value == "LIMIT_PULLBACK":
            if trade_plan.entry_price > trade_plan.current_price and trade_plan.take_profit_1 < trade_plan.current_price:
                blocked.append("Entry quality invalid for current market structure.")

        if trade_plan.entry_price and snapshot.nearest_resistance and trade_plan.take_profit_1:
            if trade_plan.take_profit_1 <= trade_plan.entry_price:
                blocked.append("Price too close to opposite level.")

        risk_status = RiskStatus.BLOCKED if blocked else RiskStatus.PASSED
        news_status = "CLEAR" if context.minutes_to_high_impact_news is None and context.minutes_since_high_impact_news is None else "NEWS_WINDOW"

        return RiskCheck(
            risk_status=risk_status,
            risk_reward=trade_plan.risk_reward,
            spread_status=spread_status,
            spread=context.spread,
            max_allowed_spread=self.limits.max_spread,
            news_status=news_status,
            volatility_status=snapshot.volatility_status,
            position_size_status="VALID",
            blocked_reasons=blocked,
        )

    def compute_position_size(self, data: PositionSizingInput) -> float:
        if data.stop_loss_distance_value <= 0 or data.value_per_point <= 0:
            return 0.0
        account_risk_amount = data.account_balance * (data.risk_percent / 100.0)
        return account_risk_amount / (data.stop_loss_distance_value * data.value_per_point)
