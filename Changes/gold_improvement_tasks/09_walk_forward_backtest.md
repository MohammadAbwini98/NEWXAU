# Task 09 — Walk-Forward Backtesting

## Objective
Add walk-forward backtesting to test the Gold signal system in a realistic way.

Normal backtesting is not enough because it may accidentally optimize to one historical period.

## Implementation Prompt
Review the current backtesting/prediction accuracy code. Add a WalkForwardBacktestService that repeatedly trains or recalibrates on one period, tests on the next unseen period, then moves forward. It should evaluate the full recommendation pipeline including models, Strategy Brain, Entry/SL/TP, Risk Engine, and validation logic.

## Walk-Forward Flow

```text
Window 1:
Train/calibrate: Jan-Mar
Test: Apr

Window 2:
Train/calibrate: Feb-Apr
Test: May

Window 3:
Train/calibrate: Mar-May
Test: Jun
```

Support configurable windows:

```text
train_months
validation_months
test_months
step_months
instrument
timeframe
```

## What Must Be Tested
The backtest must run the same pipeline as live mode:

```text
historical candles
  ↓
indicators
  ↓
model predictions or stored predictions
  ↓
dynamic model weights
  ↓
market regime
  ↓
Strategy Brain
  ↓
Entry/SL/TP plan scoring
  ↓
risk/news/session filters
  ↓
signal validation
  ↓
performance report
```

## Required Metrics
Track:

```text
total signals
recommended signals
blocked signals
win rate
BUY precision
SELL precision
profit factor
net points
average R:R
max drawdown
average win
average loss
expectancy
Sharpe-like score if available
MFE/MAE
missed entries
expired signals
model-by-model performance
performance by session
performance by regime
performance by timeframe
```

## Required Tables/Reports

### `backtest_runs`

```text
id
name
instrument
timeframe
config_json
started_at
completed_at
status
summary_json
```

### `backtest_windows`

```text
id
backtest_run_id
train_start
train_end
test_start
test_end
summary_json
```

### `backtest_signals`

```text
id
backtest_run_id
backtest_window_id
signal_snapshot_json
outcome_json
created_at
```

## API Endpoints

```text
POST /api/backtests/walk-forward/start
GET /api/backtests
GET /api/backtests/{id}
GET /api/backtests/{id}/windows
GET /api/backtests/{id}/signals
```

## Dashboard Changes
Add Backtesting page:

- Backtest run list
- Summary metrics cards
- Window-by-window performance
- Equity curve if available
- Drawdown chart if available
- Signals table
- Model performance comparison

## Important Rules

- Do not use future data in feature calculation.
- Do not randomly split time-series data.
- Ensure indicators use only candles available at that time.
- For ambiguous candle TP/SL cases, use conservative logic unless lower timeframe data exists.
- Include spread/slippage simulation.

## Integration With Current Basecode
Use existing Strategy Brain services instead of duplicating logic. The backtest should call the same core services with historical timestamps.

Suggested abstraction:

```csharp
public interface IRecommendationPipeline
{
    Task<RecommendationResult> GenerateAsync(RecommendationRequest request, CancellationToken cancellationToken);
}
```

Backtest should call this pipeline for each historical decision point.

## Tests
Add tests for:

- Walk-forward windows generated correctly
- No future data leakage
- Signal validation inside backtest
- Metrics calculation
- Backtest can run with mocked model predictions

## Acceptance Criteria

- Walk-forward backtest can run from API or command.
- Backtest uses the same Strategy Brain as live mode.
- Results are persisted and visible on dashboard.
- Metrics show performance by window, model, session, and regime.
