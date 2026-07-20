from __future__ import annotations

from typing import Iterable


def _value(values: list[float], index: int, default: float = 0.0) -> float:
    try:
        return float(values[index])
    except Exception:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(min(value, high), low)


def _normalize(values: Iterable[float]) -> tuple[float, float, float]:
    buy, sell, hold = [max(float(v), 0.0) for v in values]
    total = buy + sell + hold
    if total <= 0.0:
        return 0.33, 0.33, 0.34
    return buy / total, sell / total, hold / total


def predict_with_profile(
    feature_vector: list[float],
    tilt: float = 0.0,
    sensitivity: float = 1.0,
    hold_bias: float = 0.0,
) -> tuple[float, float, float]:
    """Baseline artifact inference over the runtime's 17-feature vector.

    This is a replaceable production adapter shape. It keeps the model artifact
    contract live until trained model weights are dropped into this directory.
    """
    return_1 = _value(feature_vector, 0)
    return_5 = _value(feature_vector, 1)
    return_20 = _value(feature_vector, 2)
    atr = max(abs(_value(feature_vector, 5)), abs(_value(feature_vector, 15)), 0.1)
    dist_ema20 = _value(feature_vector, 7) / atr
    dist_ema50 = _value(feature_vector, 8) / atr
    rsi = _value(feature_vector, 13, 50.0)
    macd_hist = _value(feature_vector, 14)
    atr_pct = abs(_value(feature_vector, 16))

    bias = 0.0
    bias += _clamp(return_1 * 180.0, -0.15, 0.15)
    bias += _clamp(return_5 * 140.0, -0.30, 0.30)
    bias += _clamp(return_20 * 90.0, -0.25, 0.25)
    bias += _clamp(dist_ema20 * 0.10, -0.18, 0.18)
    bias += _clamp(dist_ema50 * 0.08, -0.16, 0.16)
    bias += _clamp((rsi - 50.0) / 50.0, -1.0, 1.0) * 0.22
    bias += _clamp(macd_hist / atr, -1.0, 1.0) * 0.18
    bias = _clamp((bias * sensitivity) + tilt, -0.95, 0.95)

    volatility_hold_boost = 0.0
    if atr_pct < 0.03:
        volatility_hold_boost += 0.20
    elif atr_pct > 0.40:
        volatility_hold_boost += 0.25

    uncertainty_hold_boost = max(0.0, 0.15 - abs(bias)) * 0.50
    buy_raw = 0.10 + max(bias, 0.0) * 2.5
    sell_raw = 0.10 + max(-bias, 0.0) * 2.5
    hold_raw = 0.15 + hold_bias + uncertainty_hold_boost + volatility_hold_boost

    return _normalize((buy_raw, sell_raw, hold_raw))
