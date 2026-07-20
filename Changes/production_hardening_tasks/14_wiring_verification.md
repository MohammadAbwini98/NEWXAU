# Task 14 — Final Wiring Verification

## Goal

After all production-hardening tasks are implemented, verify that the entire system is correctly wired end-to-end.

## Output File

Create:

```text
/docs/final_wiring_verification.md
```

## Verification Checklist

The report must confirm:

```text
Each module is called by the correct upstream service.
Each module writes required database records.
Each module is exposed by API if needed.
Each module is visible in dashboard if needed.
Each module has logs.
Each module has tests.
No mock provider is used in production mode unless explicitly configured.
No hardcoded thresholds remain in Strategy Brain.
No generated signal is lost without validation.
No model prediction is ignored without reason.
```

## End-to-End Flow To Verify

Verify this full flow:

```text
Market Data
  -> Indicator Engine
  -> Model Ensemble
  -> Model Vote Normalizer
  -> Dynamic Model Weights
  -> Market Regime Detector
  -> Multi-Timeframe Confirmation
  -> News Filter
  -> Strategy Brain
  -> Entry/SL/TP Plan Engine
  -> Risk Engine
  -> Final Recommendation
  -> Database Persistence
  -> Dashboard API
  -> Dashboard UI
  -> Signal Validation
  -> Model Performance Tracking
  -> Dynamic Weight Update
```

## Required Sample Outputs

Include examples of:

1. Generated recommended signal
2. Blocked signal with reasons
3. Validated signal outcome
4. Model performance update
5. Dynamic weight update
6. News-blocked signal
7. Walk-forward report summary
8. Threshold optimization summary
9. Production health snapshot

## Acceptance Criteria

- Verification report exists.
- All critical modules are checked.
- Any remaining TODOs are clearly listed with reason and priority.
- The system is not marked production-ready unless all critical checks pass.
