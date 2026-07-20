# Task 03 — Dynamic Model Weighting

## Objective
Replace fixed ensemble weights with dynamic weights based on recent model performance, market regime, timeframe, session, and direction.

The system should automatically trust models that are currently performing well and reduce weight for models performing poorly.

## Implementation Prompt
Review the current ensemble weighted voting logic. Add a dynamic model weighting service that calculates the effective weight for each model at prediction time. Preserve the existing fixed weights as base weights, then apply dynamic adjustment factors.

## Weighting Formula
Use a transparent formula:

```text
effective_weight = base_weight
                 × recent_performance_factor
                 × direction_factor
                 × session_factor
                 × regime_factor
                 × confidence_calibration_factor
                 × health_factor
```

Then normalize all model weights so total equals 1.0.

## Required Table/Entity

### `model_weight_profiles`

Fields:

```text
id
model_name
base_weight
min_weight
max_weight
is_enabled
applies_to_timeframe
created_at
updated_at
```

### `model_dynamic_weights`

Fields:

```text
id
model_name
instrument
timeframe
market_regime
session
signal_type
base_weight
effective_weight
adjustment_reason_json
calculated_at
```

## Adjustment Rules

### Recent Performance Factor
Example:

```text
recent win rate >= 60% → factor 1.15
recent win rate 50%-59% → factor 1.00
recent win rate 45%-49% → factor 0.85
recent win rate < 45% → factor 0.65
```

### Direction Factor
Example:

```text
If model BUY precision is strong and current prediction is BUY:
  increase weight

If model SELL precision is weak and current prediction is SELL:
  reduce weight
```

### Session Factor
Example:

```text
If LightGBM performs well during London session:
  increase LightGBM weight during London

If Transformer performs poorly during Asian session:
  reduce Transformer weight during Asian
```

### Regime Factor
Example:

```text
TCN performs better in trending markets.
LightGBM performs better in range/filtering situations.
N-HiTS performs better for expected range forecasting.
```

## Integration With Current Basecode
Current flow should become:

```text
Model predictions generated
  ↓
Market regime detected
  ↓
ModelPerformanceTracker provides recent metrics
  ↓
DynamicModelWeightService calculates weights
  ↓
Weighted ensemble consensus is calculated
  ↓
Strategy Brain receives consensus
```

Suggested interface:

```csharp
public interface IDynamicModelWeightService
{
    Task<IReadOnlyList<ModelWeightResult>> CalculateWeightsAsync(
        ModelWeightRequest request,
        CancellationToken cancellationToken);
}
```

## Required Output
For every signal, store the actual weights used:

```json
{
  "kronos": { "base": 0.30, "effective": 0.27, "reason": "recent BUY precision below baseline" },
  "tcn": { "base": 0.25, "effective": 0.31, "reason": "strong trend-regime performance" },
  "lightgbm": { "base": 0.20, "effective": 0.23, "reason": "good London session calibration" }
}
```

## Safeguards

- Never set a model weight below `min_weight` unless the model is disabled.
- Never set a model weight above `max_weight`.
- If performance data is insufficient, use base weight.
- If model health check fails, set weight to zero and record reason.

## API Endpoints

```text
GET /api/models/weights/current
GET /api/models/weights/history
POST /api/models/weights/recalculate
PUT /api/models/weights/profile/{modelName}
```

## Dashboard Changes
Add Model Weights card:

- Base weight
- Effective weight
- Weight change indicator
- Reason for change
- Last 100-signal performance

## Tests
Add tests for:

- Weight increases after strong recent performance
- Weight decreases after weak performance
- Min/max weight boundaries
- Fallback to base weights when no metrics exist
- Health failure sets model weight to zero

## Acceptance Criteria

- Ensemble uses dynamic weights.
- Weights are persisted with each signal snapshot.
- Dashboard shows why weights changed.
- System can fall back safely to base weights.
