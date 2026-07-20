# Task 10 — Multi-Timeframe Confirmation Hardening

## Goal

Prevent 5m Gold signals from being generated without higher-timeframe context.

The system should use multiple timeframes for confirmation, entry timing, and structure awareness.

## Required Timeframes

```text
1m  = entry timing
5m  = main signal
15m = confirmation
1h  = trend context
4h  = major structure
```

## Required Per-Timeframe Analysis

For each timeframe, calculate:

```text
trend direction
momentum state
volatility state
support/resistance levels
model signal if available
indicator summary
market structure state
```

## Strategy Rules

Example BUY allow rule:

```text
Allow BUY when:
- 5m signal is BUY
- 15m is not bearish
- 1h is bullish or neutral
- entry plan is valid on 1m/5m
```

Example BUY block rule:

```text
Block BUY when:
- 5m says BUY
- 1h is strongly bearish
- price is under major 1h resistance
```

## Required Output

The module should produce a matrix:

```json
{
  "1m": { "trend": "BULLISH", "role": "ENTRY_TIMING" },
  "5m": { "signal": "BUY", "role": "MAIN_SIGNAL" },
  "15m": { "trend": "NEUTRAL", "role": "CONFIRMATION" },
  "1h": { "trend": "BULLISH", "role": "TREND_CONTEXT" },
  "4h": { "structure": "MAJOR_RESISTANCE_NEARBY", "role": "MAJOR_STRUCTURE" }
}
```

## Dashboard Requirements

Show a multi-timeframe matrix with:

- Trend per timeframe
- Signal per timeframe
- Momentum state
- Volatility state
- Support/resistance warnings
- Whether each timeframe supports or blocks the signal

## Acceptance Criteria

- Multi-timeframe data is loaded and analyzed.
- Strategy Brain uses multi-timeframe confirmation.
- Signal snapshot stores MTF matrix.
- Dashboard shows MTF matrix.
- Tests cover allow/block scenarios.
