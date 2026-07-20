# Task 04 — Market Regime Detection

## Objective
Add a Market Regime Detector that classifies current XAUUSD conditions and allows the Strategy Brain to change behavior depending on the market state.

## Implementation Prompt
Review the current indicator and market-structure modules. Add a dedicated service that classifies the current market regime using indicators, volatility, trend structure, and recent candle behavior. Wire the detected regime into model weighting, strategy scoring, entry selection, and risk filters.

## Required Regimes
Support at least:

```text
TRENDING_UP
TRENDING_DOWN
RANGING
BREAKOUT
HIGH_VOLATILITY
LOW_VOLATILITY
NEWS_SPIKE
REVERSAL_ZONE
CHOPPY
UNKNOWN
```

A signal may have one primary regime and multiple tags.

Example:

```json
{
  "primary_regime": "TRENDING_UP",
  "tags": ["HIGH_VOLATILITY", "LONDON_SESSION"],
  "confidence": 0.74
}
```

## Detection Inputs
Use existing indicators where available:

```text
EMA20/50/100/200
ADX
ATR
Bollinger Band width
Donchian channel
swing highs/lows
support/resistance distance
recent candle range
volume/tick volume
RSI/MACD
session/time
news status if available
```

## Example Regime Rules

### TRENDING_UP

```text
price > EMA50
EMA20 > EMA50
EMA50 > EMA200
ADX > 20
higher highs / higher lows detected
```

### TRENDING_DOWN

```text
price < EMA50
EMA20 < EMA50
EMA50 < EMA200
ADX > 20
lower highs / lower lows detected
```

### RANGING

```text
ADX < 18
price oscillates between support/resistance
Bollinger width normal/low
no clear higher-high/lower-low continuation
```

### BREAKOUT

```text
close above recent resistance or below support
range expansion
ATR rising
volume/tick volume spike if available
```

### CHOPPY

```text
frequent direction changes
small candles
low model agreement
overlapping candles
bad recent strategy performance
```

## Integration With Current Basecode

```text
IndicatorEngine
  ↓
MarketStructureAnalyzer
  ↓
MarketRegimeDetector
  ↓
DynamicModelWeightService
  ↓
StrategyBrain
  ↓
EntryPlanScoringEngine
```

The regime result must be included in the signal snapshot.

## Strategy Behavior by Regime

### TRENDING_UP

- Prefer BUY pullbacks.
- Penalize SELL unless reversal evidence is strong.
- Use EMA/VWAP pullback entries.

### TRENDING_DOWN

- Prefer SELL pullbacks.
- Penalize BUY unless reversal evidence is strong.

### RANGING

- Prefer support/resistance reversals.
- Avoid unconfirmed breakout entries.

### BREAKOUT

- Allow breakout entries after candle close confirmation.
- Use wider ATR-based SL.

### CHOPPY

- Block weak signals.
- Require higher confidence and better R:R.

## Database
Add regime fields to signal snapshot or dedicated table:

```text
signal_id
primary_regime
regime_confidence
regime_tags_json
regime_inputs_json
created_at
```

## API Endpoints

```text
GET /api/market/regime/current
GET /api/market/regime/history
GET /api/signals/{id}/regime
```

## Dashboard Changes
Add Market Regime card:

- Primary regime
- Confidence
- Tags
- Reasoning
- Recommended strategy mode

## Tests
Add tests for:

- Uptrend regime detection
- Downtrend regime detection
- Range detection
- Breakout detection
- Choppy detection
- Unknown fallback when data is insufficient

## Acceptance Criteria

- Every signal has a market regime snapshot.
- Strategy Brain uses regime in scoring.
- Dynamic model weighting uses regime.
- Dashboard shows current and historical regime.
