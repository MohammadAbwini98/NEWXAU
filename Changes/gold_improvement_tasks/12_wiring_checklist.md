# Task 12 — Final Wiring Checklist and End-to-End Verification

## Objective
Verify that all improvement tasks work together with the current basecode as one complete system.

## Implementation Prompt
After implementing Tasks 01–11, review the entire codebase and verify the complete data flow from market data to dashboard. Fix wiring issues, missing mappings, broken DTOs, failed jobs, null values, and inconsistent status values.

## End-to-End Flow to Verify

```text
1. Market candles are received/stored.
2. Indicators are calculated.
3. Models generate predictions.
4. Model predictions are persisted.
5. Market regime is detected.
6. Dynamic model weights are calculated.
7. Multi-timeframe confirmation is calculated.
8. Strategy Brain calculates final direction and score.
9. Entry/SL/TP candidate plans are generated and scored.
10. Risk filters run: spread, news, health, session, R:R.
11. Final recommendation is created.
12. Recommendation snapshot is persisted.
13. Dashboard shows recommendation clearly.
14. Pending signals are validated later.
15. Model performance updates after outcome.
16. Dynamic weights use updated performance.
17. Replay view can reproduce the signal decision.
18. Walk-forward backtesting uses the same pipeline.
19. Threshold optimization uses walk-forward results.
20. System health blocks unsafe recommendations.
```

## Required Consistency Checks

### Status Values
Ensure consistent enums across backend, DB, and frontend:

```text
RECOMMENDED
WEAK_RECOMMENDATION
HOLD
BLOCKED_BY_RISK
BLOCKED_BY_SPREAD
BLOCKED_BY_NEWS
BLOCKED_BY_LOW_CONFIDENCE
BLOCKED_BY_MODEL_CONFLICT
BLOCKED_BY_LOW_RISK_REWARD
BLOCKED_BY_SYSTEM_HEALTH
```

### Outcomes

```text
WIN
LOSS
PARTIAL_TP
BREAKEVEN
EXPIRED
MISSED_ENTRY
PENDING
```

### Signals

```text
BUY
SELL
HOLD
```

### Entry Types

```text
MARKET
LIMIT_PULLBACK
BREAKOUT
RETEST
REVERSAL
NONE
```

## Dashboard Verification
Fix all N/A values. A missing value should show an explanation, not just `N/A`.

Examples:

```text
No outcome yet: "Pending validation"
No news provider: "News source not configured"
No model metrics: "Insufficient historical outcomes"
No current signal: "Waiting for next 5m candle"
```

## Required Tests
Add one integration test or scripted verification for:

```text
Generate signal → save snapshot → validate outcome → update model performance → update dynamic weights → show dashboard summary
```

## Documentation
Update:

```text
docs/implementation-progress.md
docs/system-architecture.md
docs/api-endpoints.md
docs/dashboard-fields.md
docs/database-schema.md
```

## Acceptance Criteria

- Solution builds successfully.
- Existing tests pass.
- New tests pass.
- No dashboard crash.
- No unexplained N/A values.
- A signal can be traced from creation to outcome.
- A model weight can be traced to performance metrics.
- A blocked signal shows exact blocked reasons.
- Entry/SL/TP plan selection is visible and explainable.
