# Task 05 — Signal Validation Hardening

## Goal

Ensure every generated signal is persisted and later validated using real candle movement.

No signal should disappear without an outcome.

## Required Signal Fields

Every generated signal must include:

```text
signal_id
created_at
instrument
timeframe
signal_direction
status
confidence
score
entry_type
entry_price
stop_loss
take_profit_1
take_profit_2
take_profit_3
risk_reward
valid_until
model_votes_snapshot
indicator_snapshot
risk_snapshot
blocked_reasons
strategy_version
threshold_profile_id
model_weight_profile_id
```

## Validation Outcomes

The validation engine must determine:

```text
WIN
LOSS
PARTIAL_TP
BREAKEVEN
EXPIRED
MISSED_ENTRY
CANCELLED
UNKNOWN
```

## Validation Logic

For every signal, the validation engine must check future candles after signal creation:

1. Was the entry price reached?
2. Did the signal expire before entry?
3. Was SL hit first?
4. Was TP1 hit first?
5. Was TP2 hit?
6. Was TP3 hit?
7. What was the maximum favorable excursion?
8. What was the maximum adverse excursion?
9. How long did it take to reach outcome?

## Example

```text
Given BUY signal:
Entry = 2350
SL = 2345
TP1 = 2355

If future candles hit 2355 before 2345:
Outcome = WIN or PARTIAL_TP depending on configured rule.
```

## Dashboard/API Requirements

Expose:

- Recent validated signals
- Outcome counts
- Win/loss/expired/missed entry
- Signal replay details
- Validation timeline

## Acceptance Criteria

- Every signal is saved.
- Every eligible signal is validated.
- Validation uses real candle data.
- Outcomes are persisted.
- Dashboard shows validation results.
- Tests cover WIN, LOSS, EXPIRED, MISSED_ENTRY, PARTIAL_TP.
