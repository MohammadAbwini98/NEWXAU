# Task 10 — Threshold Optimization

## Objective
Add automatic threshold optimization for confidence, model agreement, ATR multipliers, RSI ranges, ADX thresholds, spread limits, R:R limits, and filter settings.

This should improve the Strategy Brain without manual guessing.

## Implementation Prompt
Review the current configuration and hard-coded thresholds. Move tunable values into configuration profiles. Add an optimizer that tests candidate parameter sets on historical data using walk-forward validation and selects robust settings based on out-of-sample performance.

## Tunable Parameters
Support optimization for:

```text
minimum_final_confidence
minimum_model_agreement
minimum_risk_reward
atr_sl_multiplier
atr_tp_multiplier
max_spread
rsi_buy_min
rsi_buy_max
rsi_sell_min
rsi_sell_max
adx_min_trend
news_block_minutes_before
news_block_minutes_after
market_regime_score_weights
entry_plan_score_weights
model_weight_adjustment_factors
```

## Optimization Process

```text
1. Define candidate parameter ranges.
2. Run walk-forward backtest for each candidate set.
3. Score each candidate by robust metrics.
4. Reject candidates that overfit or trade too rarely.
5. Save best candidate as proposed profile.
6. Require manual activation unless auto-activation is explicitly configured.
```

## Candidate Scoring Formula
Example:

```text
score = profit_factor_score
      + win_rate_score
      + drawdown_score
      + expectancy_score
      + trade_count_score
      + stability_score
      - overfit_penalty
```

Do not choose the highest win rate alone.

## Required Tables

### `strategy_parameter_profiles`

```text
id
name
instrument
timeframe
parameters_json
is_active
created_at
activated_at
```

### `optimization_runs`

```text
id
name
instrument
timeframe
search_space_json
started_at
completed_at
status
best_profile_id
summary_json
```

### `optimization_candidates`

```text
id
optimization_run_id
profile_id
metrics_json
score
rank
rejected_reason
```

## Search Methods
Start simple:

```text
Grid search for small ranges
Random search for larger ranges
```

Later optional:

```text
Bayesian optimization
Genetic algorithm
```

## Safeguards

- Never optimize on the same period used for final evaluation only.
- Use walk-forward validation.
- Penalize low trade count.
- Penalize unstable performance across windows.
- Penalize high drawdown.
- Save the previous active profile so rollback is possible.
- Do not auto-activate a profile unless explicitly configured.

## Integration With Current Basecode

```text
StrategyConfigurationProvider
  ↓
StrategyBrain uses active parameter profile
  ↓
WalkForwardBacktestService evaluates candidate profiles
  ↓
ThresholdOptimizationService selects proposed profile
  ↓
Dashboard/API allows review and activation
```

## API Endpoints

```text
POST /api/optimization/start
GET /api/optimization/runs
GET /api/optimization/runs/{id}
GET /api/optimization/runs/{id}/candidates
POST /api/strategy/profiles/{id}/activate
GET /api/strategy/profiles/active
```

## Dashboard Changes
Add Optimization page:

- Active strategy profile
- Optimization runs
- Best candidate metrics
- Candidate comparison table
- Activate profile button
- Rollback button

## Tests
Add tests for:

- Parameters loaded from active profile
- Candidate profiles generated from search space
- Candidate score calculated correctly
- Low trade count candidate penalized
- Profile activation and rollback

## Acceptance Criteria

- Strategy thresholds are configurable.
- Optimizer can evaluate candidate profiles with walk-forward backtesting.
- Best profile is saved as proposed.
- Dashboard/API can activate or rollback profiles safely.
