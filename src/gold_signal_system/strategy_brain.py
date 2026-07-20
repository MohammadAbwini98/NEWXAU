from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import EnsemblePrediction, IndicatorSnapshot, RecommendationStatus, SignalDirection, StrategyDecision
from .news_intelligence.models import StrategyNewsStateModel


@dataclass(slots=True)
class StrategyThresholdProfile:
    profile_id: int = 1
    version: int = 1
    name: str = "default"
    minimum_final_confidence: float = 0.55
    recommended_score: float = 75.0
    weak_recommendation_score: float = 60.0
    adx_threshold: float = 20.0
    minimum_risk_reward: float = 1.5
    raw: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "name": self.name,
            "minimum_final_confidence": self.minimum_final_confidence,
            "recommended_score": self.recommended_score,
            "weak_recommendation_score": self.weak_recommendation_score,
            "adx_threshold": self.adx_threshold,
            "minimum_risk_reward": self.minimum_risk_reward,
            "raw": self.raw or {},
        }


class StrategyBrain:
    """Phase 4: convert model + indicator evidence into a decision status."""

    def __init__(self, threshold_profile: StrategyThresholdProfile | None = None) -> None:
        self.threshold_profile = threshold_profile or StrategyThresholdProfile()

    def set_threshold_profile(self, threshold_profile: StrategyThresholdProfile) -> None:
        self.threshold_profile = threshold_profile

    def evaluate(
        self,
        ensemble: EnsemblePrediction,
        snapshot: IndicatorSnapshot,
        entry_quality_score: float = 50.0,
        risk_passed: bool = True,
        news_state: StrategyNewsStateModel | None = None,
    ) -> StrategyDecision:
        reasons: list[str] = []
        blocked_reasons: list[str] = []

        model_score = ensemble.ensemble_confidence * 35.0
        signal = ensemble.ensemble_signal
        trend_aligned = self._trend_confirms(signal, snapshot)
        momentum_aligned = self._momentum_confirms(signal, snapshot)
        structure_aligned = self._structure_confirms(signal, snapshot)

        trend_score = ((snapshot.trend.score / 100.0) * 15.0) if trend_aligned else 0.0
        momentum_score = ((snapshot.momentum.score / 100.0) * 10.0) if momentum_aligned else 0.0

        if snapshot.volatility_status == "VALID":
            volatility_score = 10.0
        elif snapshot.volatility_status == "HIGH":
            volatility_score = 7.0
        elif snapshot.volatility_status == "TOO_LOW":
            volatility_score = 2.0
        else:
            volatility_score = 1.0

        if structure_aligned:
            structure_score = 15.0
        elif snapshot.structure_bias == "RANGE":
            structure_score = 8.0
        else:
            structure_score = 5.0

        entry_score = (max(min(entry_quality_score, 100.0), 0.0) / 100.0) * 10.0
        risk_score = 5.0 if risk_passed else 0.0

        smc_score = 0.0
        if snapshot.smc and snapshot.smc.smc_setup_valid:
            if snapshot.smc.setup_direction == signal:
                if snapshot.smc.is_po3_time:
                    smc_score = 25.0
                    reasons.append("SMC Setup (Sweep + IFVG + DOL) perfectly aligns with model direction during PO3.")
                else:
                    smc_score = 15.0
                    reasons.append("SMC Setup aligns with model but outside optimal PO3 time (discounted).")

        # Technical misconfirmation is a score penalty, not a hard block: a confident,
        # diverse model ensemble can be right even when a lagging indicator disagrees.
        # Contradicting a *strong* indicator costs points (so the setup must clear the
        # score bar on its own merits) but no longer vetoes the trade outright.
        confirmation_penalty = 0.0
        if signal != SignalDirection.HOLD:
            if not trend_aligned and snapshot.trend.score >= 60:
                confirmation_penalty += 8.0
            if not momentum_aligned and snapshot.momentum.score >= 60:
                confirmation_penalty += 5.0
            if not structure_aligned and snapshot.structure_bias != "RANGE":
                confirmation_penalty += 8.0

        total_score = max(
            0.0,
            model_score
            + trend_score
            + momentum_score
            + volatility_score
            + structure_score
            + entry_score
            + risk_score
            + smc_score
            - confirmation_penalty,
        )
        
        final_score_before_news = total_score
        
        if news_state and news_state.active_news_weight > 0.0:
            if news_state.active_trade_bias == "BUY" and signal == SignalDirection.BUY:
                total_score += 15.0 * news_state.active_news_weight
                reasons.append(f"AI News strongly supports LONG (Weight: {news_state.active_news_weight:.2f})")
            elif news_state.active_trade_bias == "SELL" and signal == SignalDirection.SELL:
                total_score += 15.0 * news_state.active_news_weight
                reasons.append(f"AI News strongly supports SHORT (Weight: {news_state.active_news_weight:.2f})")
            elif news_state.active_trade_bias in ["BUY", "SELL"] and signal != SignalDirection.HOLD:
                total_score -= 15.0 * news_state.active_news_weight
                reasons.append(f"AI News bias ({news_state.active_trade_bias}) opposes model direction.")

        strategy_bias = "BULLISH" if signal == SignalDirection.BUY else ("BEARISH" if signal == SignalDirection.SELL else "NEUTRAL")

        if ensemble.agreement_status.value == "STRONG":
            reasons.append("Core models strongly agree on direction.")
        elif ensemble.agreement_status.value == "NORMAL":
            reasons.append("Core model agreement is acceptable.")
        elif ensemble.agreement_status.value == "MIXED":
            reasons.append("Model votes are mixed.")
        else:
            blocked_reasons.append("Model conflict is high.")

        if trend_aligned and snapshot.trend.score >= 60:
            reasons.append("Trend score supports direction.")
        elif signal != SignalDirection.HOLD and snapshot.trend.score >= 60:
            reasons.append("Trend does not confirm model direction (score penalty applied).")

        if momentum_aligned and snapshot.momentum.score >= 60:
            reasons.append("Momentum confirms continuation.")
        elif signal != SignalDirection.HOLD and snapshot.momentum.score >= 60:
            reasons.append("Momentum does not confirm model direction (score penalty applied).")

        if not structure_aligned and snapshot.structure_bias != "RANGE" and signal != SignalDirection.HOLD:
            reasons.append("Market structure does not confirm model direction (score penalty applied).")

        if snapshot.volatility_status == "TOO_LOW":
            blocked_reasons.append("ATR too low for expected movement.")
        elif snapshot.volatility_status == "EXTREME":
            blocked_reasons.append("ATR extreme without special volatility mode.")

        if snapshot.news_status != "CLEAR":
            blocked_reasons.append("High-impact news filter is active.")

        # Directional confidence = winning side's share of BUY/SELL mass, ignoring
        # the HOLD class. Well-calibrated models on near-efficient timeframes spread
        # mass across 3 classes, so max(buy,sell,hold) understates directional
        # conviction; buy/(buy+sell) measures the actual long-vs-short lean.
        directional_total = ensemble.buy_score + ensemble.sell_score
        if signal == SignalDirection.BUY and directional_total > 0:
            directional_confidence = ensemble.buy_score / directional_total
        elif signal == SignalDirection.SELL and directional_total > 0:
            directional_confidence = ensemble.sell_score / directional_total
        else:
            directional_confidence = ensemble.ensemble_confidence

        status = RecommendationStatus.HOLD
        if signal == SignalDirection.HOLD:
            status = RecommendationStatus.HOLD
        elif any("Model conflict" in msg for msg in blocked_reasons):
            status = RecommendationStatus.BLOCKED_BY_MODEL_CONFLICT
        elif any("news" in msg.lower() for msg in blocked_reasons):
            status = RecommendationStatus.BLOCKED_BY_NEWS
        elif directional_confidence < self.threshold_profile.minimum_final_confidence:
            blocked_reasons.append("Model confidence is below minimum threshold.")
            status = RecommendationStatus.BLOCKED_BY_LOW_CONFIDENCE
        elif total_score >= self.threshold_profile.recommended_score and not blocked_reasons:
            status = RecommendationStatus.RECOMMENDED
        elif self.threshold_profile.weak_recommendation_score <= total_score < self.threshold_profile.recommended_score and not blocked_reasons:
            status = RecommendationStatus.WEAK_RECOMMENDATION
        elif blocked_reasons:
            status = RecommendationStatus.BLOCKED_BY_RISK
        else:
            status = RecommendationStatus.HOLD

        model_consensus = f"{ensemble.agreement_status.value}_{signal.value}"
        indicator_bias = "BULLISH" if snapshot.trend.bias == "BULLISH" else ("BEARISH" if snapshot.trend.bias == "BEARISH" else "MIXED")

        return StrategyDecision(
            instrument=ensemble.instrument,
            timeframe=ensemble.timeframe,
            signal=signal,
            status=status,
            score=round(total_score, 2),
            confidence=ensemble.ensemble_confidence,
            strategy_bias=strategy_bias,
            model_consensus=model_consensus,
            indicator_bias=indicator_bias,
            entry_quality="GOOD" if entry_quality_score >= 70 else "AVERAGE",
            risk_status="PASSED" if risk_passed else "BLOCKED",
            reasons=reasons,
            blocked_reasons=blocked_reasons,
            news_state_id=news_state.id if news_state else None,
            news_bias=news_state.active_trade_bias if news_state else None,
            news_confidence=news_state.active_confidence if news_state else None,
            news_weight_used=news_state.active_news_weight if news_state else None,
            news_action_level=news_state.action_level if news_state else None,
            news_block_reason=news_state.reason if news_state and news_state.block_trading else None,
            final_score_before_news=round(final_score_before_news, 2),
            final_score_after_news=round(total_score, 2),
        )

    def _trend_confirms(self, signal: SignalDirection, snapshot: IndicatorSnapshot) -> bool:
        if signal == SignalDirection.BUY:
            return snapshot.trend.bias == "BULLISH"
        if signal == SignalDirection.SELL:
            return snapshot.trend.bias == "BEARISH"
        return snapshot.trend.bias == "NEUTRAL"

    def _momentum_confirms(self, signal: SignalDirection, snapshot: IndicatorSnapshot) -> bool:
        if signal == SignalDirection.BUY:
            return snapshot.momentum.bias == "POSITIVE"
        if signal == SignalDirection.SELL:
            return snapshot.momentum.bias == "NEGATIVE"
        return snapshot.momentum.bias == "MIXED"

    def _structure_confirms(self, signal: SignalDirection, snapshot: IndicatorSnapshot) -> bool:
        if signal == SignalDirection.BUY:
            return "BULLISH" in snapshot.structure_bias
        if signal == SignalDirection.SELL:
            return "BEARISH" in snapshot.structure_bias
        return snapshot.structure_bias in ("NEUTRAL", "RANGE")
