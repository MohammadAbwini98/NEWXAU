from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .contracts import Candle, IndicatorSnapshot


@dataclass(slots=True)
class MarketRegimeResult:
    primary_regime: str
    confidence: float
    tags: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    strategy_mode: str = "BALANCED"
    inputs: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def model_dump(self) -> dict[str, Any]:
        return {
            "primary_regime": self.primary_regime,
            "confidence": round(self.confidence, 4),
            "tags": self.tags,
            "reasoning": self.reasoning,
            "evidence": self.reasoning,
            "strategy_mode": self.strategy_mode,
            "inputs": self.inputs,
            "created_at": self.created_at.isoformat(),
        }


class MarketRegimeDetector:
    def detect(self, snapshot: IndicatorSnapshot, candles: list[Candle]) -> MarketRegimeResult:
        if len(candles) < 30:
            return MarketRegimeResult(
                primary_regime="UNKNOWN",
                confidence=0.2,
                tags=["INSUFFICIENT_DATA"],
                reasoning=["Fewer than 30 candles available."],
            )

        close = candles[-1].close
        highs = [c.high for c in candles[-20:]]
        lows = [c.low for c in candles[-20:]]
        ranges = [max(c.high - c.low, 0.0) for c in candles[-20:]]
        body_ratios = [abs(c.close - c.open) / max(c.high - c.low, 0.0001) for c in candles[-20:]]
        avg_range = sum(ranges) / len(ranges)
        atr_percentile_proxy = snapshot.atr / max(avg_range, 0.0001)
        avg_body_ratio = sum(body_ratios) / len(body_ratios)
        latest_range = ranges[-1]
        ema20 = float(snapshot.raw_json.get("ema20", close))
        ema50 = float(snapshot.raw_json.get("ema50", ema20))
        ema200 = float(snapshot.raw_json.get("ema200", ema50))
        adx = float(snapshot.raw_json.get("adx", snapshot.trend.score / 4.0))

        tags: list[str] = []
        reasons: list[str] = []
        primary = "UNKNOWN"
        confidence = 0.45
        mode = "BALANCED"

        if snapshot.news_status != "CLEAR":
            primary = "NEWS_SPIKE"
            confidence = 0.8
            tags.append("NEWS_RISK")
            reasons.append("News status is not clear.")
            mode = "NEWS_PROTECTION"
        elif close > max(highs[:-1]) and latest_range > avg_range * 1.2:
            primary = "BREAKOUT"
            confidence = 0.72
            tags.append("RANGE_EXPANSION")
            reasons.append("Close broke above recent resistance with range expansion.")
            mode = "BREAKOUT_CONFIRMATION"
        elif close < min(lows[:-1]) and latest_range > avg_range * 1.2:
            primary = "BREAKOUT"
            confidence = 0.72
            tags.append("BREAKDOWN")
            reasons.append("Close broke below recent support with range expansion.")
            mode = "BREAKOUT_CONFIRMATION"
        elif close > ema50 and ema20 >= ema50 >= ema200 and adx >= 20 and "BULLISH" in snapshot.structure_bias:
            primary = "TRENDING_UP"
            confidence = 0.76
            reasons.append("EMA alignment, ADX, and structure support an uptrend.")
            mode = "BUY_PULLBACKS"
        elif close < ema50 and ema20 <= ema50 <= ema200 and adx >= 20 and "BEARISH" in snapshot.structure_bias:
            primary = "TRENDING_DOWN"
            confidence = 0.76
            reasons.append("EMA alignment, ADX, and structure support a downtrend.")
            mode = "SELL_PULLBACKS"
        elif adx < 18 or snapshot.structure_bias == "RANGE":
            primary = "RANGING"
            confidence = 0.66
            reasons.append("Low ADX or range structure suggests mean reversion.")
            mode = "RANGE_REVERSIONS"
        elif self._is_choppy(candles[-12:]):
            primary = "CHOPPY"
            confidence = 0.63
            reasons.append("Recent candles overlap and change direction frequently.")
            mode = "DEFENSIVE"
        else:
            primary = "LOW_VOLATILITY" if snapshot.volatility_status == "TOO_LOW" else "HIGH_VOLATILITY" if snapshot.volatility_status == "EXTREME" else "UNKNOWN"
            confidence = 0.55
            reasons.append(f"Volatility status is {snapshot.volatility_status}.")

        if snapshot.volatility_status in {"HIGH", "EXTREME"}:
            tags.append("HIGH_VOLATILITY")
            reasons.append(f"ATR/range proxy is {atr_percentile_proxy:.2f}.")
        if snapshot.volatility_status == "TOO_LOW":
            tags.append("LOW_VOLATILITY")
            reasons.append("ATR is below movement threshold.")
        if avg_body_ratio < 0.35:
            tags.append("LOW_BODY_RATIO")
            if primary == "UNKNOWN":
                primary = "CHOPPY"
                confidence = max(confidence, 0.58)
                mode = "DEFENSIVE"
            reasons.append("Recent candle bodies are small relative to ranges.")
        if snapshot.nearest_resistance and abs(snapshot.nearest_resistance - close) <= snapshot.atr:
            tags.append("RESISTANCE_NEARBY")
            if primary in {"TRENDING_UP", "RANGING"}:
                tags.append("REVERSAL_ZONE")
        if snapshot.nearest_support and abs(close - snapshot.nearest_support) <= snapshot.atr:
            tags.append("SUPPORT_NEARBY")
            if primary in {"TRENDING_DOWN", "RANGING"}:
                tags.append("REVERSAL_ZONE")
        if snapshot.session_name:
            tags.append(f"{snapshot.session_name}_SESSION")

        return MarketRegimeResult(
            primary_regime=primary,
            confidence=confidence,
            tags=tags,
            reasoning=reasons,
            strategy_mode=mode,
            inputs={
                "close": close,
                "ema20": ema20,
                "ema50": ema50,
                "ema200": ema200,
                "adx": adx,
                "avg_range_20": avg_range,
                "atr_percentile_proxy": atr_percentile_proxy,
                "avg_body_ratio": avg_body_ratio,
                "latest_range": latest_range,
                "structure_bias": snapshot.structure_bias,
            },
        )

    def _is_choppy(self, candles: list[Candle]) -> bool:
        if len(candles) < 6:
            return False
        directions = [1 if c.close >= c.open else -1 for c in candles]
        flips = sum(1 for left, right in zip(directions, directions[1:]) if left != right)
        overlap_count = 0
        for left, right in zip(candles, candles[1:]):
            if min(left.high, right.high) >= max(left.low, right.low):
                overlap_count += 1
        return flips >= len(candles) // 2 and overlap_count >= len(candles) // 2
