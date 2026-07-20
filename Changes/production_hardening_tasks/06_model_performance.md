# Task 06 — Model Performance Hardening

## Goal

Track each model separately from final Strategy Brain performance.

The system must know which models are actually useful and under which conditions.

## Required Model Prediction Fields

For each model prediction, store:

```text
model_name
model_version
timeframe
prediction_time
predicted_signal
predicted_confidence
actual_outcome
direction_correct
confidence_bucket
market_regime
session
volatility_regime
news_proximity
```

## Required Metrics

Calculate:

```text
overall accuracy
BUY precision
SELL precision
HOLD accuracy
win rate when model agreed with final signal
win rate when model disagreed
performance by session
performance by market regime
performance by confidence bucket
performance by timeframe
```

## Integration With Signal Validation

When a final signal is validated, update related model prediction performance.

Example:

```text
Final signal: BUY
Outcome: WIN
Kronos predicted BUY -> correct/agreed
TCN predicted SELL -> disagreed/wrong for this signal
LightGBM predicted BUY -> correct/agreed
```

## Integration With Dynamic Weighting

Model performance must feed the Dynamic Model Weighting module.

The weighting module should be able to query:

```text
model performance over last N validated signals
model performance by session
model performance by regime
model BUY precision
model SELL precision
confidence calibration bucket
```

## Dashboard Requirements

Show:

- Model performance cards
- BUY precision per model
- SELL precision per model
- Confidence bucket reliability
- Performance by session/regime
- Model agreement vs final result

## Acceptance Criteria

- Every model prediction is persisted.
- Model performance is updated after signal validation.
- Metrics are available through API/dashboard.
- Dynamic weighting uses real model performance data.
