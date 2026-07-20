# Task 13 — Testing Requirements

## Goal

Add deterministic tests for all critical production-hardening modules.

The goal is to prevent silent failures in signal generation, validation, risk calculation, and dashboard APIs.

## Required Test Areas

Add tests for:

```text
Signal validation
Entry/SL/TP calculation
Risk/reward calculation
News blocking
Market regime detection
Dynamic model weighting
Threshold profile loading
Model vote normalization
Strategy Brain final decision
Dashboard API DTOs
Database persistence
Multi-timeframe confirmation
Production health status
```

## Example Signal Validation Test

```text
Given BUY signal with:
Entry = 2350
SL = 2345
TP1 = 2355

And future candles hit TP1 before SL

Then outcome should be WIN or PARTIAL_TP depending on configured rules.
```

## Example Risk Test

```text
Given entry = 2350
SL = 2348
TP = 2353

Risk = 2
Reward = 3
Risk/Reward = 1.5

If minimum required R:R = 2.0
Then signal should be blocked by low risk/reward.
```

## Example News Test

```text
Given high-impact USD CPI event at 15:30
And current time is 15:10
And block_before_minutes = 30

Then new signal should be BLOCKED_BY_NEWS.
```

## Example Dynamic Weight Test

```text
Given TCN performance improves over last 100 validated signals
And max_change_per_update = 0.03

Then TCN weight should increase by no more than 0.03.
```

## Acceptance Criteria

- Tests are deterministic.
- Tests do not depend on live market data.
- Critical modules have coverage.
- Strategy decisions are reproducible.
- Dashboard DTOs are tested for missing/null values.
