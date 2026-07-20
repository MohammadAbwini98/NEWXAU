# Task 07 — Dynamic Model Weighting Hardening

## Goal

Make dynamic model weighting safe, explainable, versioned, and based on real validated performance.

## Safety Rules

1. Use rolling performance windows.
2. Never allow one model to dominate completely.
3. Set minimum and maximum weight per model.
4. Weight changes must be gradual.
5. Store every weight profile version.
6. Allow rollback.
7. Explain why weights changed.

## Required Weight Profile Fields

```text
profile_id
version
is_active
created_at
model_weights_json
reason_summary
performance_window
min_weight
max_weight
max_change_per_update
```

## Weight Update Example

```json
{
  "model": "TCN",
  "old_weight": 0.25,
  "new_weight": 0.28,
  "reason": "TCN BUY precision improved to 63% over last 100 validated signals during London session."
}
```

## Inputs

Use model performance metrics from:

- Recent win rate
- BUY precision
- SELL precision
- Session performance
- Market regime performance
- Volatility regime performance
- Confidence bucket reliability
- Drawdown impact

## Strategy Brain Integration

The Strategy Brain must load the active model weight profile.

Do not use hardcoded model weights inside the Strategy Brain.

## Dashboard Requirements

Show:

- Current model weights
- Weight history
- Latest weight change reasons
- Model performance behind the weights
- Active profile version
- Rollback option if supported

## Acceptance Criteria

- Weights are based on validated results.
- Weight changes are bounded.
- Profiles are versioned and persisted.
- Strategy Brain uses active profile.
- Dashboard explains weight changes.
