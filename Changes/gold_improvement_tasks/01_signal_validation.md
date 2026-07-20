# Task 01 — Signal Validation and Outcome Tracking

## Objective
Add a validation layer that records every generated signal and later determines whether it was a real WIN, LOSS, PARTIAL_TP, BREAKEVEN, EXPIRED, or MISSED_ENTRY.

This is the foundation for all future improvements. Without this, the system cannot learn which recommendations are actually good.

## Implementation Prompt
Review the current codebase and find where final recommendation signals are created, saved, displayed, and optionally executed. Add a complete signal lifecycle tracking system that stores the original recommendation snapshot and later validates the outcome using future candles/trades.

Do not change the existing signal-generation logic unless needed for wiring. Add this as a measurable layer around the current Strategy Brain output.

## Required Signal Lifecycle

```text
CREATED
  ↓
RECOMMENDED / BLOCKED / HOLD
  ↓
WAITING_FOR_ENTRY if limit/pullback/breakout entry
  ↓
ENTRY_TRIGGERED or MISSED_ENTRY
  ↓
TP1_HIT / TP2_HIT / TP3_HIT / SL_HIT / EXPIRED
  ↓
WIN / LOSS / PARTIAL_TP / BREAKEVEN / EXPIRED
```

## Required Database Tables or Entities
Create or extend tables/entities similar to:

### `recommended_signals`
Stores the final recommendation.

Fields:

```text
id
instrument
timeframe
signal_type: BUY/SELL/HOLD
status: RECOMMENDED/BLOCKED/HOLD
entry_type: MARKET/LIMIT_PULLBACK/BREAKOUT/REVERSAL
entry_price
current_price_at_signal
stop_loss
take_profit_1
take_profit_2
take_profit_3
risk_reward
confidence
score
grade
valid_until
created_at
```

### `signal_snapshots`
Stores the full decision context as JSON.

Fields:

```text
id
signal_id
model_votes_json
model_weights_json
indicator_summary_json
market_structure_json
risk_filters_json
blocked_reasons_json
entry_plan_json
raw_recommendation_json
created_at
```

### `signal_outcomes`
Stores what happened after the signal.

Fields:

```text
id
signal_id
outcome: WIN/LOSS/PARTIAL_TP/BREAKEVEN/EXPIRED/MISSED_ENTRY
entry_triggered_at
entry_triggered_price
highest_price_after_signal
lowest_price_after_signal
exit_price
exit_reason
pnl_points
pnl_percent
max_favorable_excursion
max_adverse_excursion
validated_at
validation_window_candles
```

## Validation Logic
Implement a scheduled/background validator.

For each non-finalized signal:

1. Load future candles after `created_at`.
2. Check whether entry was triggered.
3. If entry was not triggered before expiry, mark `MISSED_ENTRY`.
4. If entry was triggered, check whether SL or TP was hit first.
5. Handle multiple TPs:
   - TP1 hit only then reversal to SL = `PARTIAL_TP`
   - TP2/TP3 hit = `WIN`
   - SL hit before TP = `LOSS`
6. Store MFE and MAE.

## BUY Validation Rules

```text
Entry triggered if candle low <= entry_price <= candle high
TP hit if candle high >= take_profit_n
SL hit if candle low <= stop_loss
```

## SELL Validation Rules

```text
Entry triggered if candle low <= entry_price <= candle high
TP hit if candle low <= take_profit_n
SL hit if candle high >= stop_loss
```

## Edge Case: Same Candle Hits TP and SL
If both TP and SL are hit in the same candle, use conservative logic:

- For backtesting/validation, assume SL first unless lower timeframe candle data is available.
- Add a field: `ambiguous_candle = true`.

## Integration With Current Basecode
Wire this after the current final recommendation is built:

```text
FinalRecommendationBuilder
  ↓
SignalPersistenceService
  ↓
SignalOutcomeValidator background job
```

The existing dashboard should continue to work. Add new endpoints rather than breaking old ones.

## API Endpoints
Add or extend:

```text
GET /api/signals/recent
GET /api/signals/{id}
GET /api/signals/{id}/snapshot
GET /api/signals/{id}/outcome
POST /api/signals/validate-pending
```

## Dashboard Changes
Show outcome badges:

```text
WIN
LOSS
PARTIAL_TP
MISSED_ENTRY
EXPIRED
BREAKEVEN
```

Add a Recent Signal Outcomes card.

## Tests
Add tests for:

- BUY TP hit
- BUY SL hit
- SELL TP hit
- SELL SL hit
- missed limit entry
- expired signal
- TP and SL same candle conservative handling

## Acceptance Criteria

- Every final recommendation is persisted.
- Every persisted signal has a snapshot.
- Pending signals are validated automatically.
- Outcome is visible on dashboard/API.
- No existing signal-generation behavior is broken.
