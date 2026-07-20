# Task 06 — Multi-Timeframe Confirmation

## Objective
Add multi-timeframe confirmation so the 5m Gold signal is not generated in isolation.

Recommended structure:

```text
1m  = entry timing
5m  = main signal
15m = confirmation
1h  = trend context
4h  = major structure
```

## Implementation Prompt
Review current candle storage, indicator calculation, and signal-generation scheduling. Add a MultiTimeframeConfirmationService that loads recent candles and indicators for multiple timeframes, classifies alignment, and provides a confirmation score to the Strategy Brain.

## Required Timeframes
Support at least:

```text
1m
5m
15m
1h
4h
```

Allow configuration to enable/disable each timeframe.

## Confirmation Output

```json
{
  "main_timeframe": "5m",
  "signal": "BUY",
  "alignment_score": 78,
  "status": "ALIGNED",
  "timeframes": {
    "1m": { "role": "ENTRY_TIMING", "bias": "BULLISH", "score": 70 },
    "5m": { "role": "MAIN_SIGNAL", "bias": "BULLISH", "score": 82 },
    "15m": { "role": "CONFIRMATION", "bias": "BULLISH", "score": 76 },
    "1h": { "role": "TREND_CONTEXT", "bias": "BULLISH", "score": 80 },
    "4h": { "role": "MAJOR_STRUCTURE", "bias": "NEUTRAL", "score": 55 }
  },
  "blocked_reasons": []
}
```

## Bias Classification
Each timeframe should classify:

```text
BULLISH
BEARISH
NEUTRAL
CHOPPY
INSUFFICIENT_DATA
```

Use indicators and structure:

```text
EMA alignment
ADX
market structure
support/resistance
RSI/MACD
swing highs/lows
ATR regime
```

## Confirmation Rules

### BUY Signal
Prefer:

```text
5m bullish
15m bullish or neutral
1h bullish or neutral
1m gives acceptable entry timing
4h not strongly bearish near resistance
```

Block or penalize:

```text
1h strongly bearish
4h at major resistance
15m strong SELL signal
1m entry timing weak or overextended
```

### SELL Signal
Prefer:

```text
5m bearish
15m bearish or neutral
1h bearish or neutral
1m gives acceptable entry timing
4h not strongly bullish near support
```

## Integration With Current Basecode

```text
MarketDataService loads candles by timeframe
  ↓
IndicatorEngine calculates per-timeframe indicators
  ↓
MultiTimeframeConfirmationService calculates alignment
  ↓
StrategyBrain scoring uses alignment score
  ↓
EntryPlanScoringEngine uses 1m timing and higher timeframe structure
```

## Database
Add to signal snapshot:

```text
multi_timeframe_summary_json
multi_timeframe_alignment_score
multi_timeframe_status
```

Optional table:

### `signal_timeframe_confirmations`

```text
id
signal_id
timeframe
role
bias
score
reason_json
created_at
```

## API Endpoints

```text
GET /api/market/timeframes/current
GET /api/signals/{id}/timeframe-confirmation
```

## Dashboard Changes
Add Multi-Timeframe panel:

- 1m, 5m, 15m, 1h, 4h cards
- Bias badge
- Score
- Key reason
- Overall alignment score

## Tests
Add tests for:

- BUY allowed when 5m/15m/1h align
- BUY penalized when 1h bearish
- SELL allowed when higher timeframes align
- Signal blocked when major timeframe conflicts strongly
- Fallback when a timeframe has insufficient data

## Acceptance Criteria

- Every signal has multi-timeframe confirmation data.
- Strategy Brain uses alignment score.
- Dashboard shows timeframe agreement/conflict.
