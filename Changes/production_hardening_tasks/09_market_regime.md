# Task 09 — Market Regime Detection Hardening

## Goal

Make market regime detection real and evidence-based, not only label-based.

The Strategy Brain should apply different rules depending on the current Gold market regime.

## Required Regimes

Detect:

```text
TRENDING_UP
TRENDING_DOWN
RANGING
CHOPPY
BREAKOUT
HIGH_VOLATILITY
LOW_VOLATILITY
NEWS_SPIKE
REVERSAL_ZONE
```

## Evidence Inputs

Use:

```text
ADX
EMA alignment
ATR percentile
Bollinger Band width
swing highs/lows
support/resistance proximity
candle body/range ratio
recent directional consistency
volume/tick-volume spike if available
news proximity
```

## Strategy Rules By Regime

Example behavior:

```text
TRENDING_UP:
- Prefer BUY pullbacks
- Penalize SELL signals

TRENDING_DOWN:
- Prefer SELL pullbacks
- Penalize BUY signals

RANGING:
- Prefer support/resistance reversal
- Reduce breakout confidence

CHOPPY:
- Block weak signals

BREAKOUT:
- Allow momentum entries
- Require volume/ATR confirmation

NEWS_SPIKE:
- Block normal strategy mode
```

## Required Output

The regime detector should return:

```json
{
  "regime": "TRENDING_UP",
  "confidence": 0.74,
  "evidence": [
    "EMA20 > EMA50 > EMA200",
    "ADX above 25",
    "Higher highs and higher lows detected"
  ]
}
```

## Dashboard Requirements

Show:

- Current market regime
- Regime confidence
- Evidence behind regime
- Regime history
- Strategy rule applied because of regime

## Acceptance Criteria

- Regime is calculated from real indicators/structure.
- Strategy Brain uses regime result.
- Regime evidence is stored in signal snapshot.
- Dashboard shows regime and evidence.
- Tests cover at least trending, ranging, choppy, and high volatility cases.
