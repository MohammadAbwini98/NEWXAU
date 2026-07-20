from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import Candle, SignalDirection




@dataclass(slots=True)
class MultiTimeframeResult:
    main_timeframe: str
    signal: str
    alignment_score: float
    status: str
    timeframes: dict[str, dict[str, Any]] = field(default_factory=dict)
    blocked_reasons: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "main_timeframe": self.main_timeframe,
            "signal": self.signal,
            "alignment_score": round(self.alignment_score, 2),
            "status": self.status,
            "timeframes": self.timeframes,
            "blocked_reasons": self.blocked_reasons,
        }


class MultiTimeframeConfirmationService:
    def evaluate(
        self,
        signal: SignalDirection,
        candles_by_timeframe: dict[str, list[Candle]],
        main_timeframe: str = "5m",
    ) -> MultiTimeframeResult:
        tf_results: dict[str, dict[str, Any]] = {}
        weighted_score = 0.0
        total_weight = 0.0
        blocked: list[str] = []
        
        if main_timeframe == "15m":
            roles = {
                "5m": "ENTRY_TIMING",
                "15m": "MAIN_SIGNAL",
                "1h": "CONFIRMATION",
                "4h": "TREND_CONTEXT",
            }
            weights = {"5m": 0.15, "15m": 0.40, "1h": 0.25, "4h": 0.20}
        else:
            roles = {
                "1m": "ENTRY_TIMING",
                "5m": "MAIN_SIGNAL",
                "15m": "CONFIRMATION",
                "1h": "TREND_CONTEXT",
                "4h": "MAJOR_STRUCTURE",
            }
            weights = {"1m": 0.15, "5m": 0.30, "15m": 0.25, "1h": 0.20, "4h": 0.10}

        for timeframe, role in roles.items():
            candles = candles_by_timeframe.get(timeframe, [])
            item = self._classify(timeframe, role, candles, signal)
            tf_results[timeframe] = item
            weight = weights.get(timeframe, 0.0)
            total_weight += weight
            weighted_score += self._alignment_points(signal, item["bias"], item["score"]) * weight

        alignment = weighted_score / total_weight if total_weight else 0.0
        if signal == SignalDirection.BUY:
            if tf_results.get("1h", {}).get("bias") == "BEARISH":
                blocked.append("1h timeframe is strongly bearish against BUY.")
            if tf_results.get("4h", {}).get("bias") == "BEARISH" and tf_results["4h"]["score"] >= 70:
                blocked.append("4h major structure conflicts with BUY.")
        elif signal == SignalDirection.SELL:
            if tf_results.get("1h", {}).get("bias") == "BULLISH":
                blocked.append("1h timeframe is strongly bullish against SELL.")
            if tf_results.get("4h", {}).get("bias") == "BULLISH" and tf_results["4h"]["score"] >= 70:
                blocked.append("4h major structure conflicts with SELL.")

        if signal == SignalDirection.HOLD:
            status = "NEUTRAL"
        elif blocked:
            status = "CONFLICT"
        elif alignment >= 70:
            status = "ALIGNED"
        elif alignment >= 50:
            status = "MIXED"
        else:
            status = "CONFLICT"

        return MultiTimeframeResult(
            main_timeframe=main_timeframe,
            signal=signal.value,
            alignment_score=alignment,
            status=status,
            timeframes=tf_results,
            blocked_reasons=blocked,
        )

    def _classify(self, timeframe: str, role: str, candles: list[Candle], signal: SignalDirection) -> dict[str, Any]:
        if len(candles) < 10:
            return {
                "role": role,
                "bias": "INSUFFICIENT_DATA",
                "trend": "INSUFFICIENT_DATA",
                "momentum": "INSUFFICIENT_DATA",
                "volatility": "INSUFFICIENT_DATA",
                "support": None,
                "resistance": None,
                "supports_signal": False,
                "blocks_signal": False,
                "score": 0.0,
                "reason": "Not enough candles for timeframe confirmation.",
            }
        closes = [c.close for c in candles[-30:]]
        recent = closes[-1]
        support = min(c.low for c in candles[-20:])
        resistance = max(c.high for c in candles[-20:])
        ranges = [c.high - c.low for c in candles[-20:]]
        avg_range = sum(ranges) / len(ranges)
        volatility = "HIGH" if ranges[-1] > avg_range * 1.4 else "LOW" if ranges[-1] < avg_range * 0.6 else "NORMAL"
        fast = sum(closes[-5:]) / min(5, len(closes))
        slow = sum(closes[-20:]) / min(20, len(closes))
        direction_score = min(abs(fast - slow) / max(recent, 0.01) * 8000.0, 100.0)
        if fast > slow * 1.0005:
            bias = "BULLISH"
        elif fast < slow * 0.9995:
            bias = "BEARISH"
        elif self._is_choppy(candles[-10:]):
            bias = "CHOPPY"
            direction_score = max(direction_score, 45.0)
        else:
            bias = "NEUTRAL"
            direction_score = max(direction_score, 55.0)
        wanted = "BULLISH" if signal == SignalDirection.BUY else "BEARISH" if signal == SignalDirection.SELL else "NEUTRAL"
        opposite = "BEARISH" if signal == SignalDirection.BUY else "BULLISH" if signal == SignalDirection.SELL else ""
        supports = bias == wanted or (bias == "NEUTRAL" and signal != SignalDirection.HOLD)
        blocks = bias == opposite and direction_score >= 55
        return {
            "role": role,
            "bias": bias,
            "trend": bias,
            "momentum": "POSITIVE" if closes[-1] > closes[-3] else "NEGATIVE" if closes[-1] < closes[-3] else "FLAT",
            "volatility": volatility,
            "support": round(support, 4),
            "resistance": round(resistance, 4),
            "support_resistance_warning": (
                "MAJOR_RESISTANCE_NEARBY" if signal == SignalDirection.BUY and resistance - recent < avg_range
                else "MAJOR_SUPPORT_NEARBY" if signal == SignalDirection.SELL and recent - support < avg_range
                else "NONE"
            ),
            "supports_signal": supports,
            "blocks_signal": blocks,
            "score": round(direction_score, 2),
            "reason": f"{timeframe} fast/slow close average classified as {bias}.",
        }

    def _alignment_points(self, signal: SignalDirection, bias: str, score: float) -> float:
        if bias == "INSUFFICIENT_DATA":
            return 35.0
        if signal == SignalDirection.HOLD:
            return 60.0 if bias in {"NEUTRAL", "CHOPPY"} else 40.0
        wanted = "BULLISH" if signal == SignalDirection.BUY else "BEARISH"
        opposite = "BEARISH" if signal == SignalDirection.BUY else "BULLISH"
        if bias == wanted:
            return 65.0 + min(score, 35.0)
        if bias == opposite:
            return max(15.0, 55.0 - score)
        if bias == "CHOPPY":
            return 35.0
        return 55.0

    def _is_choppy(self, candles: list[Candle]) -> bool:
        if len(candles) < 6:
            return False
        directions = [1 if c.close >= c.open else -1 for c in candles]
        flips = sum(1 for left, right in zip(directions, directions[1:]) if left != right)
        return flips >= len(candles) // 2
