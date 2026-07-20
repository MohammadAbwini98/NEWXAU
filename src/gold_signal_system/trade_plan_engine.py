from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import EntryType, IndicatorSnapshot, SignalDirection, TradePlan


@dataclass(slots=True)
class EntryPlanCandidate:
    plan_id: str
    signal_type: str
    entry_type: EntryType
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_points: float
    reward_points: float
    risk_reward: float
    entry_distance_from_current: float
    atr_multiple_sl: float
    atr_multiple_tp: float
    structure_alignment_score: float
    model_alignment_score: float
    risk_score: float
    execution_probability: float
    final_plan_score: float
    expected_fill_probability: float
    invalid_if_price_reaches: float | None = None
    plan_expiry_minutes: int = 15
    production_plan_type: str = "MARKET_ENTRY"
    selected: bool = False
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "signal_type": self.signal_type,
            "entry_type": self.entry_type.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "risk_points": self.risk_points,
            "reward_points": self.reward_points,
            "risk_reward": self.risk_reward,
            "entry_distance_from_current": self.entry_distance_from_current,
            "atr_multiple_sl": self.atr_multiple_sl,
            "atr_multiple_tp": self.atr_multiple_tp,
            "structure_alignment_score": self.structure_alignment_score,
            "model_alignment_score": self.model_alignment_score,
            "risk_score": self.risk_score,
            "execution_probability": self.execution_probability,
            "expected_fill_probability": self.expected_fill_probability,
            "invalid_if_price_reaches": self.invalid_if_price_reaches,
            "plan_expiry_minutes": self.plan_expiry_minutes,
            "production_plan_type": self.production_plan_type,
            "final_plan_score": self.final_plan_score,
            "selected": self.selected,
            "rejection_reason": self.rejection_reason,
            "metadata": self.metadata,
        }


class EntrySlTpEngine:
    """Phase 5: convert direction into tradable entry/SL/TP plan."""

    def generate_trade_plan(
        self,
        direction: SignalDirection,
        snapshot: IndicatorSnapshot,
        current_price: float,
        ensemble_confidence: float,
        market_regime: str = "UNKNOWN",
    ) -> TradePlan:
        if direction not in (SignalDirection.BUY, SignalDirection.SELL):
            raise ValueError("Trade plan can only be generated for BUY or SELL")
        if direction not in (SignalDirection.BUY, SignalDirection.SELL):
            raise ValueError("Trade plan can only be generated for BUY or SELL")

        candidates = self.generate_candidate_plans(direction, snapshot, current_price, ensemble_confidence, market_regime)
        selected = self.select_plan(candidates)
        entry_type = selected.entry_type
        entry_price = selected.entry_price
        atr = max(snapshot.atr, 0.1)
        stop_loss = self._stop_loss(direction, entry_type, entry_price, snapshot, atr)

        risk = max(abs(entry_price - stop_loss), 0.01)
        take_profit_1, take_profit_2, take_profit_3 = self._take_profits(
            direction,
            entry_type,
            entry_price,
            risk,
            snapshot,
            atr,
        )

        reward = abs(take_profit_2 - entry_price)
        risk_reward = reward / risk if risk else 0.0
        quality_score = self._entry_quality_score(
            direction,
            entry_price,
            current_price,
            snapshot,
            risk_reward,
            atr,
            entry_type,
        )

        return TradePlan(
            entry_type=entry_type,
            entry_price=round(entry_price, 4),
            current_price=round(current_price, 4),
            stop_loss=round(stop_loss, 4),
            take_profit_1=round(take_profit_1, 4),
            take_profit_2=round(take_profit_2, 4),
            take_profit_3=round(take_profit_3, 4),
            risk=round(risk, 4),
            reward=round(reward, 4),
            risk_reward=round(risk_reward, 4),
            entry_quality_score=round(quality_score, 2),
            valid_for_minutes=self._valid_for_minutes(snapshot.timeframe),
            sl_method="ATR_PLUS_STRUCTURE",
            tp_method="RR_PLUS_ATR_PLUS_STRUCTURE",
            reason=self._reason_text(entry_type, direction),
        )

    def generate_candidate_plans(
        self,
        direction: SignalDirection,
        snapshot: IndicatorSnapshot,
        current_price: float,
        ensemble_confidence: float,
        market_regime: str = "UNKNOWN",
    ) -> list[EntryPlanCandidate]:
        if direction not in (SignalDirection.BUY, SignalDirection.SELL):
            return []

        atr = max(snapshot.atr, 0.1)
        candidates: list[EntryPlanCandidate] = []
        types_to_try = [EntryType.MARKET, EntryType.LIMIT_PULLBACK, EntryType.BREAKOUT, EntryType.RETEST, EntryType.REVERSAL]
        if snapshot.smc and snapshot.smc.smc_setup_valid and snapshot.smc.setup_direction == direction:
            types_to_try.append(EntryType.SMC_IFVG)

        for entry_type in types_to_try:
            entry = self._entry_price(direction, entry_type, snapshot, current_price, atr)
            stop = self._stop_loss(direction, entry_type, entry, snapshot, atr)
            risk = max(abs(entry - stop), 0.01)
            tp1, tp2, tp3 = self._take_profits(direction, entry_type, entry, risk, snapshot, atr)
            reward = abs(tp2 - entry)
            rr = reward / risk if risk else 0.0
            score, rejection = self._score_candidate(
                direction=direction,
                entry_type=entry_type,
                entry_price=entry,
                current_price=current_price,
                snapshot=snapshot,
                risk_reward=rr,
                risk=risk,
                reward=reward,
                atr=atr,
                ensemble_confidence=ensemble_confidence,
                market_regime=market_regime,
            )
            candidates.append(
                EntryPlanCandidate(
                    plan_id=f"{direction.value}_{entry_type.value}",
                    signal_type=direction.value,
                    entry_type=entry_type,
                    entry_price=round(entry, 4),
                    stop_loss=round(stop, 4),
                    take_profit_1=round(tp1, 4),
                    take_profit_2=round(tp2, 4),
                    take_profit_3=round(tp3, 4),
                    risk_points=round(risk, 4),
                    reward_points=round(reward, 4),
                    risk_reward=round(rr, 4),
                    entry_distance_from_current=round(abs(entry - current_price), 4),
                    atr_multiple_sl=round(risk / atr, 4),
                    atr_multiple_tp=round(reward / atr, 4),
                    structure_alignment_score=round(self._structure_score(direction, snapshot, entry), 2),
                    model_alignment_score=round(ensemble_confidence * 100.0, 2),
                    risk_score=round(min(rr / 2.0, 1.0) * 100.0, 2),
                    execution_probability=round(self._execution_probability(entry_type, entry, current_price, atr), 2),
                    expected_fill_probability=round(self._execution_probability(entry_type, entry, current_price, atr), 2),
                    invalid_if_price_reaches=round(stop, 4),
                    plan_expiry_minutes=self._valid_for_minutes(snapshot.timeframe),
                    production_plan_type=self._production_plan_type(entry_type, snapshot),
                    final_plan_score=round(score, 2),
                    rejection_reason=rejection,
                    metadata={"market_regime": market_regime, "reason": self._reason_text(entry_type, direction)},
                )
            )

        selected = self.select_plan(candidates)
        for candidate in candidates:
            candidate.selected = candidate.plan_id == selected.plan_id
            if candidate.selected:
                candidate.rejection_reason = None
        return candidates

    def select_plan(self, candidates: list[EntryPlanCandidate]) -> EntryPlanCandidate:
        if not candidates:
            raise ValueError("No entry plan candidates available")
        valid = [candidate for candidate in candidates if candidate.rejection_reason is None]
        pool = valid or candidates
        return max(pool, key=lambda item: item.final_plan_score)

    def candidate_to_trade_plan(
        self,
        candidate: EntryPlanCandidate,
        current_price: float,
        valid_for_minutes: int,
    ) -> TradePlan:
        return TradePlan(
            entry_type=candidate.entry_type,
            entry_price=candidate.entry_price,
            current_price=round(current_price, 4),
            stop_loss=candidate.stop_loss,
            take_profit_1=candidate.take_profit_1,
            take_profit_2=candidate.take_profit_2,
            take_profit_3=candidate.take_profit_3,
            risk=candidate.risk_points,
            reward=candidate.reward_points,
            risk_reward=candidate.risk_reward,
            entry_quality_score=candidate.final_plan_score,
            valid_for_minutes=valid_for_minutes,
            sl_method="ATR_PLUS_STRUCTURE",
            tp_method="RR_PLUS_ATR_PLUS_STRUCTURE",
            reason=candidate.metadata.get("reason", "Selected by entry plan scoring."),
        )

    def _choose_entry_type(
        self,
        direction: SignalDirection,
        snapshot: IndicatorSnapshot,
        confidence: float,
    ) -> EntryType:
        structure = snapshot.structure_bias

        if confidence >= 0.72 and snapshot.momentum.score >= 70:
            return EntryType.MARKET
        if (direction == SignalDirection.BUY and "BREAKOUT" in structure) or (
            direction == SignalDirection.SELL and "BREAKDOWN" in structure
        ):
            return EntryType.BREAKOUT
        if "HH_HL" in structure or "LH_LL" in structure:
            return EntryType.LIMIT_PULLBACK
        if "RANGE" in structure:
            return EntryType.RETEST
        return EntryType.REVERSAL

    def _entry_price(
        self,
        direction: SignalDirection,
        entry_type: EntryType,
        snapshot: IndicatorSnapshot,
        current_price: float,
        atr: float,
    ) -> float:
        ema20 = float(snapshot.raw_json.get("ema20", current_price))

        if entry_type == EntryType.MARKET or entry_type == EntryType.SMC_IFVG:
            return current_price

        if direction == SignalDirection.BUY:
            if entry_type == EntryType.LIMIT_PULLBACK:
                return min(current_price - atr * 0.35, ema20)
            if entry_type == EntryType.BREAKOUT:
                return current_price + atr * 0.10
            if entry_type == EntryType.RETEST:
                return max(snapshot.nearest_support or (current_price - atr), current_price - atr * 0.45)
            return current_price - atr * 0.5

        if entry_type == EntryType.LIMIT_PULLBACK:
            return max(current_price + atr * 0.35, ema20)
        if entry_type == EntryType.BREAKOUT:
            return current_price - atr * 0.10
        if entry_type == EntryType.RETEST:
            return min(snapshot.nearest_resistance or (current_price + atr), current_price + atr * 0.45)
        return current_price + atr * 0.5

    def _stop_loss(
        self,
        direction: SignalDirection,
        entry_type: EntryType,
        entry_price: float,
        snapshot: IndicatorSnapshot,
        atr: float,
    ) -> float:
        buffer = atr * 0.15

        if entry_type == EntryType.SMC_IFVG and snapshot.smc and snapshot.smc.active_ifvgs:
            # Place SL below/above the IFVG
            ifvg = snapshot.smc.active_ifvgs[0]
            if direction == SignalDirection.BUY:
                return min(ifvg.bottom - buffer, entry_price - atr * 0.5)
            else:
                return max(ifvg.top + buffer, entry_price + atr * 0.5)

        if direction == SignalDirection.BUY:
            structure_sl = (snapshot.nearest_support or entry_price - atr * 2.0) - buffer
            atr_sl = entry_price - atr * 1.6
            return min(structure_sl, atr_sl)

        structure_sl = (snapshot.nearest_resistance or entry_price + atr * 2.0) + buffer
        atr_sl = entry_price + atr * 1.6
        return max(structure_sl, atr_sl)

    def _take_profits(
        self,
        direction: SignalDirection,
        entry_type: EntryType,
        entry_price: float,
        risk: float,
        snapshot: IndicatorSnapshot,
        atr: float,
    ) -> tuple[float, float, float]:
        sign = 1.0 if direction == SignalDirection.BUY else -1.0

        tp1 = entry_price + sign * risk * 1.0
        tp2 = entry_price + sign * risk * 2.0

        if entry_type == EntryType.SMC_IFVG and snapshot.smc:
            if snapshot.smc.active_htf_fvgs:
                # TP1 is 50% of HTF Gap
                fvg = snapshot.smc.active_htf_fvgs[0]
                eq = (fvg.top + fvg.bottom) / 2.0
                if (direction == SignalDirection.BUY and eq > entry_price) or (direction == SignalDirection.SELL and eq < entry_price):
                    tp1 = eq
            if snapshot.smc.dol:
                # TP2/TP3 is DOL
                tp2 = snapshot.smc.dol.price
                tp3 = tp2
        else:
            structure_target = snapshot.nearest_resistance if direction == SignalDirection.BUY else snapshot.nearest_support
            atr_target = entry_price + sign * atr * 3.0

            if structure_target is None:
                tp3 = atr_target
            else:
                if direction == SignalDirection.BUY:
                    tp3 = max(atr_target, structure_target)
                else:
                    tp3 = min(atr_target, structure_target)

            if direction == SignalDirection.BUY:
                tp3 = max(tp3, tp2 + max(atr * 0.25, risk * 0.5))
            else:
                tp3 = min(tp3, tp2 - max(atr * 0.25, risk * 0.5))

        return tp1, tp2, tp3

    def _entry_quality_score(
        self,
        direction: SignalDirection,
        entry_price: float,
        current_price: float,
        snapshot: IndicatorSnapshot,
        risk_reward: float,
        atr: float,
        entry_type: EntryType,
    ) -> float:
        score = 25.0

        if risk_reward >= 2.0:
            score += 30.0
        elif risk_reward >= 1.5:
            score += 18.0

        ema20 = float(snapshot.raw_json.get("ema20", current_price))
        extension = abs(current_price - ema20)
        if extension <= atr * 1.2:
            score += 15.0

        if snapshot.volatility_status == "VALID":
            score += 10.0

        if direction == SignalDirection.BUY and snapshot.nearest_resistance:
            if snapshot.nearest_resistance - entry_price > atr:
                score += 10.0
        if direction == SignalDirection.SELL and snapshot.nearest_support:
            if entry_price - snapshot.nearest_support > atr:
                score += 10.0

        if entry_type in (EntryType.LIMIT_PULLBACK, EntryType.RETEST):
            score += 10.0

        return max(min(score, 100.0), 0.0)

    def _valid_for_minutes(self, timeframe: str) -> int:
        return {
            "1m": 3,
            "5m": 15,
            "15m": 45,
            "1h": 180,
        }.get(timeframe, 15)

    def _reason_text(self, entry_type: EntryType, direction: SignalDirection) -> str:
        if entry_type == EntryType.MARKET:
            return f"Strong {direction.value} momentum and model agreement."
        if entry_type == EntryType.LIMIT_PULLBACK:
            return "Pullback entry improves risk/reward versus immediate market entry."
        if entry_type == EntryType.BREAKOUT:
            return "Breakout confirmation supports continuation entry."
        if entry_type == EntryType.RETEST:
            return "Retest entry seeks confirmation at reclaimed level."
        if entry_type == EntryType.SMC_IFVG:
            return "SMC 4-step setup confirmed (Sweep + IFVG + DOL)."
        return "Reversal setup detected near major structure level."

    def _score_candidate(
        self,
        direction: SignalDirection,
        entry_type: EntryType,
        entry_price: float,
        current_price: float,
        snapshot: IndicatorSnapshot,
        risk_reward: float,
        risk: float,
        reward: float,
        atr: float,
        ensemble_confidence: float,
        market_regime: str,
    ) -> tuple[float, str | None]:
        rejection: str | None = None
        model_alignment = ensemble_confidence * 20.0
        regime_alignment = self._regime_score(entry_type, market_regime) * 0.15
        structure = self._structure_score(direction, snapshot, entry_price) * 0.20
        rr_score = min(risk_reward / 2.0, 1.0) * 20.0
        volatility = 10.0 if snapshot.volatility_status in {"VALID", "HIGH"} and 0.4 <= risk / atr <= 4.0 else 4.0
        execution = self._execution_probability(entry_type, entry_price, current_price, atr) * 0.10
        spread_slippage = 5.0 if abs(entry_price - current_price) <= atr * 2.0 else 2.0
        score = model_alignment + regime_alignment + structure + rr_score + volatility + execution + spread_slippage

        if risk_reward < 1.5:
            rejection = "Risk/reward below 1.5."
            score = min(score, 49.0)
        if risk < atr * 0.30:
            rejection = "Stop loss too close to ATR noise."
            score = min(score, 45.0)
        if entry_type == EntryType.MARKET and abs(current_price - float(snapshot.raw_json.get("ema20", current_price))) > atr * 1.8:
            rejection = "Market entry is overextended from EMA20."
            score = min(score, 55.0)
        return max(min(score, 100.0), 0.0), rejection

    def _production_plan_type(self, entry_type: EntryType, snapshot: IndicatorSnapshot) -> str:
        if entry_type == EntryType.MARKET:
            return "MARKET_ENTRY"
        if entry_type == EntryType.LIMIT_PULLBACK:
            return "PULLBACK_TO_EMA"
        if entry_type == EntryType.RETEST:
            return "SUPPORT_RESISTANCE_RETEST"
        if entry_type == EntryType.BREAKOUT:
            return "BREAKOUT_ENTRY"
        if entry_type == EntryType.SMC_IFVG:
            return "SMC_AMD_ENTRY"
        return "STRUCTURE_ENTRY" if "HH_HL" in snapshot.structure_bias or "LH_LL" in snapshot.structure_bias else "PULLBACK_TO_VWAP"

    def _structure_score(self, direction: SignalDirection, snapshot: IndicatorSnapshot, entry_price: float) -> float:
        score = 50.0
        if direction == SignalDirection.BUY and "BULLISH" in snapshot.structure_bias:
            score += 25.0
        if direction == SignalDirection.SELL and "BEARISH" in snapshot.structure_bias:
            score += 25.0
        if direction == SignalDirection.BUY and snapshot.nearest_resistance and snapshot.nearest_resistance - entry_price > snapshot.atr:
            score += 15.0
        if direction == SignalDirection.SELL and snapshot.nearest_support and entry_price - snapshot.nearest_support > snapshot.atr:
            score += 15.0
        return max(min(score, 100.0), 0.0)

    def _regime_score(self, entry_type: EntryType, market_regime: str) -> float:
        if market_regime in {"TRENDING_UP", "TRENDING_DOWN"} and entry_type == EntryType.LIMIT_PULLBACK:
            return 95.0
        if market_regime == "BREAKOUT" and entry_type in {EntryType.BREAKOUT, EntryType.RETEST}:
            return 95.0
        if market_regime == "RANGING" and entry_type in {EntryType.RETEST, EntryType.REVERSAL}:
            return 90.0
        if market_regime == "CHOPPY" and entry_type == EntryType.MARKET:
            return 35.0
        return 65.0

    def _execution_probability(self, entry_type: EntryType, entry_price: float, current_price: float, atr: float) -> float:
        distance = abs(entry_price - current_price)
        if entry_type == EntryType.MARKET:
            return 95.0
        if distance <= atr * 0.35:
            return 82.0
        if distance <= atr * 0.75:
            return 68.0
        return 48.0
