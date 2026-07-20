# Task 05 — Entry, SL, TP Plan Scoring

## Objective
Improve Entry/SL/TP by generating multiple candidate trade plans, scoring them, and selecting the safest plan with the best trade quality.

The system must not blindly use one entry or one fixed stop/target calculation.

## Implementation Prompt
Review the current EntryPriceEngine, StopLossEngine, TakeProfitEngine, and RiskRewardCalculator. Refactor or extend them so they generate multiple candidate plans and score each plan. The selected plan should be saved with reasons, and rejected plans should also be saved for debugging.

## Required Candidate Plans
Generate these when relevant:

```text
MARKET_ENTRY
LIMIT_PULLBACK_ENTRY
BREAKOUT_ENTRY
RETEST_ENTRY
REVERSAL_ENTRY
NO_TRADE_PLAN
```

## Candidate Plan Fields

```text
plan_id
signal_type
entry_type
entry_price
stop_loss
take_profit_1
take_profit_2
take_profit_3
risk_points
reward_points
risk_reward
entry_distance_from_current
atr_multiple_sl
atr_multiple_tp
structure_alignment_score
model_alignment_score
risk_score
execution_probability
final_plan_score
selected
rejection_reason
```

## Scoring Components
Use a 100-point score:

```text
Model alignment: 20
Trend/regime alignment: 15
Market structure: 20
Risk/reward: 20
Volatility/ATR suitability: 10
Execution probability: 10
Spread/slippage quality: 5
```

## Plan Selection Rules

- Reject plans with R:R below minimum, for example 1.5.
- Prefer R:R >= 2.0.
- Reject plans where SL is too close to spread/noise.
- Reject plans where TP is directly blocked by nearby support/resistance.
- Reject market entry if price is overextended.
- Prefer pullback entry in trend regimes.
- Prefer breakout/retest entry in breakout regimes.
- Prefer reversal entry only near strong support/resistance with confirmation.

## Entry Logic

### BUY Plan Examples

```text
Market entry:
entry = current ask

Pullback entry:
entry = nearest valid support zone / EMA20 / VWAP / broken resistance retest

Breakout entry:
entry = resistance level + buffer after candle close confirmation
```

### SELL Plan Examples

```text
Market entry:
entry = current bid

Pullback entry:
entry = nearest valid resistance zone / EMA20 / VWAP / broken support retest

Breakout entry:
entry = support level - buffer after candle close confirmation
```

## Stop Loss Logic
Use combined SL:

```text
ATR SL
structure SL
support/resistance buffer
spread buffer
volatility regime multiplier
```

For BUY:

```text
SL below swing low/support, not closer than minimum ATR multiple
```

For SELL:

```text
SL above swing high/resistance, not closer than minimum ATR multiple
```

## Take Profit Logic
Use combined TP:

```text
1R / 2R / 3R
default TP1/TP2/TP3
next support/resistance
N-HiTS/PatchTST expected range
ATR target
previous high/low
```

## Integration With Current Basecode

```text
StrategyBrain decides directional candidate
  ↓
EntryPlanScoringEngine generates plans
  ↓
RiskEngine validates plans
  ↓
FinalRecommendationBuilder selects best valid plan
  ↓
SignalPersistenceService saves selected and rejected plans
```

## Database
Create or extend:

### `signal_entry_plans`

Fields:

```text
id
signal_id
entry_type
entry_price
stop_loss
take_profit_1
take_profit_2
take_profit_3
risk_reward
plan_score
selected
rejection_reason
plan_json
created_at
```

## API Endpoints

```text
GET /api/signals/{id}/entry-plans
GET /api/signals/{id}/selected-plan
```

## Dashboard Changes
Add Entry Plan panel:

- Selected plan
- Entry type
- Entry price
- SL / TP1 / TP2 / TP3
- R:R
- Plan score
- Rejected plans with reasons

## Tests
Add tests for:

- Pullback plan selected over market plan when market entry has weak R:R
- Breakout plan selected in breakout regime
- Plan rejected when R:R below minimum
- SL calculation using ATR and structure
- TP adjusted when resistance/support is nearby

## Acceptance Criteria

- Multiple plans are generated for each directional signal.
- Every plan is scored.
- Selected plan and rejected plans are saved.
- Dashboard shows selected and rejected plans.
