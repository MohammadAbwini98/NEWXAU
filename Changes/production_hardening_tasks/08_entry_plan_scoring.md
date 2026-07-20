# Task 08 — Entry / SL / TP Plan Scoring Hardening

## Goal

Upgrade Entry/SL/TP logic so it generates multiple candidate plans, scores them, and selects the safest valid plan.

The Strategy Brain must not rely on a single fixed entry method.

## Required Candidate Plans

Generate these candidate plans:

```text
MARKET_ENTRY
PULLBACK_TO_EMA
PULLBACK_TO_VWAP
SUPPORT_RESISTANCE_RETEST
BREAKOUT_ENTRY
STRUCTURE_ENTRY
```

## Required Fields Per Plan

Each plan must calculate:

```text
entry_price
stop_loss
take_profit_1
take_profit_2
take_profit_3
risk_reward
entry_distance_from_current_price
expected_fill_probability
invalid_if_price_reaches
plan_expiry
score
rejection_reason
```

## Scoring Criteria

Score each plan based on:

- Risk/reward ratio
- Distance from current price
- Entry quality
- Stop loss quality
- TP realism
- Expected fill probability
- Support/resistance safety
- ATR compatibility
- Model expected movement
- Spread cost

## Blocking Rules

A signal must be blocked if no plan passes:

```text
minimum risk/reward
maximum SL distance
minimum expected movement
spread rules
support/resistance safety rules
```

Required statuses:

```text
BLOCKED_NO_VALID_ENTRY_PLAN
BLOCKED_LOW_RISK_REWARD
BLOCKED_SL_TOO_WIDE
BLOCKED_SL_TOO_TIGHT
```

## Strategy Brain Integration

The Strategy Brain flow should be:

```text
Model consensus -> Direction candidate
Indicator confirmation -> Context
EntryPlanEngine -> Candidate plans
RiskEngine -> Validate plans
Strategy Brain -> Select best plan or block
```

## Dashboard Requirements

Show:

- Selected entry plan
- Rejected plans
- Rejection reasons
- Entry/SL/TP levels
- Risk/reward
- Plan expiry

## Acceptance Criteria

- Multiple entry plans are generated.
- Invalid plans are rejected with reasons.
- Best valid plan is selected.
- Signal is blocked if no valid plan exists.
- Dashboard shows selected and rejected plans.
- Tests cover plan scoring and blocking.
