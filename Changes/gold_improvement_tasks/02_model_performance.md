# Task 02 — Model-by-Model Performance Tracking

## Objective
Track the performance of each model separately, not only the final strategy.

The system must know whether Kronos, TCN, LightGBM, PatchTST, CNN-LSTM, GRU, LSTM, Transformer, and N-HiTS are helping or hurting.

## Implementation Prompt
Review the current ensemble/model prediction code. For every generated signal, store each model prediction, confidence, direction, forecasted return/range when available, and whether that model agreed with the final outcome. Then calculate model-level metrics by timeframe, direction, session, market regime, and confidence bucket.

## Required Model Prediction Storage
Create or extend a table/entity:

### `model_signal_predictions`

Fields:

```text
id
signal_id
model_name
model_version
instrument
timeframe
predicted_signal: BUY/SELL/HOLD
confidence
raw_score
predicted_return
predicted_high
predicted_low
forecast_horizon
weight_used
created_at
```

## Required Model Outcome Storage
Create or extend:

### `model_prediction_outcomes`

Fields:

```text
id
model_prediction_id
signal_id
was_direction_correct
was_profitable
actual_outcome
actual_return
error_abs
error_squared
evaluated_at
```

## How It Should Work

```text
Model Ensemble runs
  ↓
Each model output is normalized
  ↓
Each model prediction is saved
  ↓
Final Strategy Brain creates signal
  ↓
Signal Outcome Validator validates signal
  ↓
Model Performance Tracker updates model statistics
```

## Metrics to Calculate
Track at least:

```text
model_win_rate
buy_precision
sell_precision
hold_accuracy
average_confidence
confidence_calibration
profit_factor_contribution
average_pnl_points
max_drawdown_contribution
number_of_predictions
number_of_recommended_predictions
```

Break down by:

```text
timeframe
session
market_regime
volatility_regime
signal_type
confidence_bucket
model_version
```

## Confidence Buckets
Use buckets like:

```text
0.50-0.60
0.60-0.70
0.70-0.80
0.80-0.90
0.90-1.00
```

For each bucket, calculate actual win rate. This will later be used for calibration.

## Integration With Current Basecode
Add a `ModelPerformanceTracker` that listens after signal outcome validation.

```text
SignalOutcomeValidator
  ↓
ModelPerformanceTracker.UpdateMetrics(signalId)
```

If the codebase uses domain events, publish:

```text
SignalOutcomeFinalizedEvent
```

and handle it with:

```text
ModelPerformanceTrackerHandler
```

## API Endpoints

```text
GET /api/models/performance
GET /api/models/performance/{modelName}
GET /api/models/performance/summary
GET /api/models/performance/by-regime
GET /api/models/performance/confidence-calibration
```

## Dashboard Changes
Add Model Performance panel:

- Model name
- Current weight
- Win rate
- BUY precision
- SELL precision
- Recent performance
- Confidence calibration
- Last prediction

Use green for strong models, amber for weak/uncertain, red for poor performers.

## Tests
Add tests for:

- Saving all model predictions for one signal
- Updating model outcome after signal validation
- Calculating BUY precision
- Calculating SELL precision
- Calculating confidence bucket win rates

## Acceptance Criteria

- Every model vote is persisted.
- Model performance can be calculated separately.
- Dashboard/API shows model-by-model results.
- Model metrics are queryable by timeframe, direction, and market regime.
