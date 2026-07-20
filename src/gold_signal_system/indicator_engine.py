from __future__ import annotations

import math
from statistics import mean, pstdev

from .contracts import Candle, IndicatorGroupScore, IndicatorSnapshot
from .market_sessions import get_gold_market_session


def _sma(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    window = values[-period:] if len(values) >= period else values
    return sum(window) / len(window)


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2.0 / (period + 1.0)
    ema = values[0]
    for value in values[1:]:
        ema = (value * k) + (ema * (1.0 - k))
    return ema


def _rsi(values: list[float], period: int = 14) -> float:
    if len(values) < 2:
        return 50.0
    deltas = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]
    avg_gain = _sma(gains, period)
    avg_loss = _sma(losses, period)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    macd_line = ema12 - ema26

    history = []
    for i in range(max(2, len(values) - 50), len(values) + 1):
        sub = values[:i]
        history.append(_ema(sub, 12) - _ema(sub, 26))
    signal = _ema(history, 9)
    hist = macd_line - signal
    return macd_line, signal, hist


def _atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0

    true_ranges: list[float] = []
    for i in range(1, len(candles)):
        current = candles[i]
        prev = candles[i - 1]
        tr = max(
            current.high - current.low,
            abs(current.high - prev.close),
            abs(current.low - prev.close),
        )
        true_ranges.append(tr)

    if not true_ranges:
        return 0.0
    return _sma(true_ranges, period)


def _realized_volatility(closes: list[float], period: int = 20) -> float:
    if len(closes) < 2:
        return 0.0
    returns = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev == 0:
            continue
        returns.append(math.log(closes[i] / prev))
    if not returns:
        return 0.0
    window = returns[-period:] if len(returns) >= period else returns
    return pstdev(window) * math.sqrt(len(window))


def _structure_bias(candles: list[Candle]) -> str:
    if len(candles) < 6:
        return "NEUTRAL"

    recent = candles[-6:]
    highs = [c.high for c in recent]
    lows = [c.low for c in recent]

    if highs[-1] > highs[-2] > highs[-3] and lows[-1] > lows[-2] > lows[-3]:
        return "BULLISH_HH_HL"
    if highs[-1] < highs[-2] < highs[-3] and lows[-1] < lows[-2] < lows[-3]:
        return "BEARISH_LH_LL"
    if highs[-1] > max(highs[:-1]):
        return "BULLISH_BREAKOUT"
    if lows[-1] < min(lows[:-1]):
        return "BEARISH_BREAKDOWN"
    return "RANGE"


def _nearest_support_resistance(candles: list[Candle], current_price: float) -> tuple[float, float]:
    lows = [c.low for c in candles[-120:]]
    highs = [c.high for c in candles[-120:]]

    supports = [x for x in lows if x <= current_price]
    resistances = [x for x in highs if x >= current_price]

    nearest_support = max(supports) if supports else min(lows)
    nearest_resistance = min(resistances) if resistances else max(highs)
    return nearest_support, nearest_resistance


def _candle_pattern_bias(candles: list[Candle]) -> str:
    if len(candles) < 2:
        return "NEUTRAL"

    last = candles[-1]
    prev = candles[-2]
    body = abs(last.close - last.open)
    span = max(last.high - last.low, 1e-8)
    wick_ratio = (span - body) / span

    bullish_engulfing = (
        prev.close < prev.open
        and last.close > last.open
        and last.close >= prev.open
        and last.open <= prev.close
    )
    bearish_engulfing = (
        prev.close > prev.open
        and last.close < last.open
        and last.open >= prev.close
        and last.close <= prev.open
    )

    if bullish_engulfing:
        return "BULLISH_ENGULFING"
    if bearish_engulfing:
        return "BEARISH_ENGULFING"
    if wick_ratio > 0.65 and body / span < 0.35:
        return "REJECTION"
    return "NEUTRAL"


class FeatureIndicatorEngine:
    """Phase 2: build features and technical indicator snapshots."""

    def compute_features(self, candles: list[Candle]) -> dict[str, float | str]:
        if not candles:
            return {}

        closes = [c.close for c in candles]
        current = closes[-1]

        r1 = (closes[-1] / closes[-2] - 1.0) if len(closes) > 1 and closes[-2] != 0 else 0.0
        r5 = (closes[-1] / closes[-6] - 1.0) if len(closes) > 6 and closes[-6] != 0 else 0.0
        r20 = (closes[-1] / closes[-21] - 1.0) if len(closes) > 21 and closes[-21] != 0 else 0.0

        atr = _atr(candles, 14)
        vol = _realized_volatility(closes, 20)
        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)

        return {
            "return_1": r1,
            "return_5": r5,
            "return_20": r20,
            "rolling_mean_20": _sma(closes, 20),
            "rolling_std_20": pstdev(closes[-20:]) if len(closes) >= 20 else (pstdev(closes) if len(closes) > 1 else 0.0),
            "atr_14": atr,
            "realized_volatility": vol,
            "distance_to_ema20": current - ema20,
            "distance_to_ema50": current - ema50,
            "session": get_gold_market_session(candles[-1].candle_time),
            "candle_pattern": _candle_pattern_bias(candles),
        }

    def build_indicator_snapshot(
        self,
        instrument: str,
        timeframe: str,
        candles: list[Candle],
        news_status: str = "CLEAR",
    ) -> IndicatorSnapshot:
        if len(candles) < 20:
            raise ValueError("Need at least 20 candles for indicator snapshot")

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        current_price = closes[-1]
        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)
        ema100 = _ema(closes, 100)
        ema200 = _ema(closes, 200)
        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
        rsi = _rsi(closes, 14)
        _, _, macd_hist = _macd(closes)
        atr = _atr(candles, 14)
        avg_range = mean([(h - l) for h, l in zip(highs[-20:], lows[-20:])])
        atr_pct = (atr / current_price) * 100 if current_price else 0.0

        nearest_support, nearest_resistance = _nearest_support_resistance(candles, current_price)
        structure_bias = _structure_bias(candles)
        session_name = get_gold_market_session(candles[-1].candle_time)

        trend_score = 0.0
        trend_reasons: list[str] = []
        if current_price > ema20:
            trend_score += 15
            trend_reasons.append("Price above EMA20")
        if current_price > ema50:
            trend_score += 15
            trend_reasons.append("Price above EMA50")
        if current_price > ema200:
            trend_score += 20
            trend_reasons.append("Price above EMA200")
        if ema20 > ema50 > ema200:
            trend_score += 30
            trend_reasons.append("EMA20 > EMA50 > EMA200")
        if current_price > sma50:
            trend_score += 10
        if current_price > sma200:
            trend_score += 10
        trend_score = min(trend_score, 100.0)
        trend_bias = "BULLISH" if trend_score >= 60 else ("BEARISH" if trend_score <= 40 else "NEUTRAL")

        momentum_score = 0.0
        momentum_reasons: list[str] = []
        if 45 <= rsi <= 70:
            momentum_score += 45
            momentum_reasons.append("RSI in bullish momentum zone")
        elif 30 <= rsi < 45:
            momentum_score += 25
        elif rsi > 70:
            momentum_score += 10
            momentum_reasons.append("RSI overbought")
        else:
            momentum_score += 15

        if macd_hist > 0:
            momentum_score += 35
            momentum_reasons.append("MACD histogram positive")
        else:
            momentum_score += 10

        returns = self.compute_features(candles)
        if float(returns.get("return_5", 0.0)) > 0:
            momentum_score += 20
        momentum_score = min(momentum_score, 100.0)
        momentum_bias = "POSITIVE" if momentum_score >= 60 else ("NEGATIVE" if momentum_score <= 40 else "MIXED")

        # ATR%-of-price scales with sqrt(bar duration) (random-walk), so the volatility
        # bands must scale with the timeframe; otherwise thresholds tuned on 5m flag
        # normal 1h/4h volatility as EXTREME. Base bands are defined for 5m.
        tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}.get(timeframe, 5)
        vol_scale = math.sqrt(tf_minutes / 5.0)
        volatility_status = "VALID"
        if atr_pct < 0.03 * vol_scale:
            volatility_status = "TOO_LOW"
        elif atr_pct > 0.40 * vol_scale:
            volatility_status = "EXTREME"
        elif atr_pct > 0.25 * vol_scale:
            volatility_status = "HIGH"

        raw = {
            "ema20": ema20,
            "ema50": ema50,
            "ema100": ema100,
            "ema200": ema200,
            "sma50": sma50,
            "sma200": sma200,
            "rsi14": rsi,
            "macd_hist": macd_hist,
            "atr14": atr,
            "atr_pct": atr_pct,
            "average_candle_range": avg_range,
            "trend_reasons": trend_reasons,
            "momentum_reasons": momentum_reasons,
            "pattern": returns.get("candle_pattern", "NEUTRAL"),
        }

        return IndicatorSnapshot(
            instrument=instrument,
            timeframe=timeframe,
            snapshot_time=candles[-1].candle_time,
            trend=IndicatorGroupScore(bias=trend_bias, score=trend_score),
            momentum=IndicatorGroupScore(bias=momentum_bias, score=momentum_score),
            volatility_status=volatility_status,
            atr=atr,
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            structure_bias=structure_bias,
            session_name=session_name,
            news_status=news_status,
            raw_json=raw,
        )
