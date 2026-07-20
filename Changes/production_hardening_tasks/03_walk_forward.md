# Task 03 — Walk-Forward Backtesting Upgrade

## Goal

Upgrade walk-forward backtesting from an MVP pipeline into a production-ready validation framework.

The system must support both strategy-only walk-forward testing and future real model retraining.

## Mode A — Strategy-Only Walk-Forward

This mode uses existing saved model predictions or current model outputs.

It is used to test:

- Strategy Brain
- Risk Engine
- Entry/SL/TP Engine
- Thresholds
- Model weights
- News filters
- Market regime rules
- Multi-timeframe confirmation

## Mode B — Model-Retraining Walk-Forward

This mode must define the full structure and extension points for real model retraining.

Even if real heavy training is not fully implemented now, the code must be prepared so real training can be plugged in cleanly.

Required parameters:

```text
Train window
Validation window
Test window
Step size
Model list
Feature config
Threshold config
Output artifact path
Metrics output path
```

## Required Output Folder

Create walk-forward reports under:

```text
/reports/walk_forward/
```

Required files:

```text
summary.json
folds.csv
trades.csv
model_metrics.csv
strategy_metrics.csv
recommendations.md
```

## Required Fold Metrics

Each fold should track:

```text
fold_number
train_start
train_end
test_start
test_end
number_of_signals
number_of_trades
win_rate
profit_factor
max_drawdown
average_rr
buy_precision
sell_precision
blocked_signals
best_thresholds
model_weights_used
```

## Strategy Integration

Walk-forward must use the same production pipeline as live/demo signals:

```text
Historical Candles
  -> Indicator Engine
  -> Model Prediction Loader/Runner
  -> Strategy Brain
  -> Entry/SL/TP Engine
  -> Risk Engine
  -> Signal Validation
  -> Metrics
```

Do not create a separate fake strategy path.

## Acceptance Criteria

- Walk-forward can run over historical periods.
- Results are saved into report files.
- Fold-by-fold metrics are available.
- Strategy-only mode works now.
- Model-retraining mode has clean extension points.
- Dashboard/API can read latest walk-forward summary.
