# Task 04 — Threshold Optimization Upgrade

## Goal

Upgrade threshold optimization from simple grid scoring into a safer, versioned, rollback-capable optimization system.

## Required Data Split

Optimization must support three separate periods:

```text
Train optimization period
Validation period
Unseen test period
```

Never optimize and report final results on the same data only.

## Thresholds to Optimize

Support optimization of:

```text
minimum_final_confidence
minimum_model_agreement
minimum_risk_reward
max_spread
atr_minimum
atr_maximum
adx_threshold
rsi_buy_min
rsi_buy_max
rsi_sell_min
rsi_sell_max
news_block_minutes_before
news_block_minutes_after
model_weight_adjustment_limits
```

## Database Requirements

Create or update these entities/tables:

```text
threshold_profiles
threshold_optimization_runs
threshold_optimization_results
```

## Versioning Requirements

Each threshold profile must have:

```text
profile_id
version
name
is_active
created_at
created_by
source_run_id
config_json
notes
```

## Rollback Requirements

The system must allow rollback to a previous threshold profile.

The Strategy Brain must load the active threshold profile from configuration/database, not from hardcoded values.

## Overfitting Protection

The optimization report must show:

```text
training score
validation score
unseen test score
selected threshold profile
reason for selection
warnings if validation/test result diverges too much
```

## Acceptance Criteria

- No hardcoded strategy thresholds remain in the Strategy Brain.
- Active threshold profile is loaded dynamically.
- Optimization output is persisted.
- Previous profiles are preserved.
- Rollback is possible.
- Report separates train/validation/test results.
