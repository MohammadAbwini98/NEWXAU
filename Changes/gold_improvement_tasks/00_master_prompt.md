# Master Implementation Prompt — Gold Signal System Improvements

You are working inside the existing Gold/XAUUSD signal recommendation codebase. Your job is to improve the already implemented professional recommendation system without breaking the existing flow.

## Main Goal
Implement the next improvement roadmap in sequence:

1. Signal validation and outcome tracking
2. Model-by-model performance tracking
3. Dynamic model weighting
4. Market regime detection
5. Improved Entry/SL/TP plan scoring
6. Multi-timeframe confirmation
7. News filter
8. Dashboard transparency and replay mode
9. Walk-forward backtesting
10. Threshold optimization

## Most Important Principle
Every recommendation must become measurable and explainable:

- Every signal must be stored and later validated.
- Every model must be evaluated separately.
- Every blocked signal must explain why.
- Every Entry/SL/TP plan must be scored.
- Every final recommendation must be reproducible from saved snapshots.

## Required Working Style
Before coding, review the current codebase and identify existing modules for:

- Signal generation
- Model ensemble
- Strategy Brain
- Indicator Engine
- Entry/SL/TP calculation
- Risk Engine
- Database persistence
- Dashboard API
- Frontend dashboard
- Scheduled jobs/background workers

Do not rewrite the whole project. Wire the improvements into the current architecture using clean services, interfaces, DTOs, database migrations, and tests.

## Expected Architecture After Improvements

```text
Market Data
  ↓
Indicator Engine
  ↓
Model Ensemble
  ↓
Model Performance Tracker
  ↓
Dynamic Model Weighting
  ↓
Market Regime Detector
  ↓
Strategy Brain
  ↓
Entry/SL/TP Plan Generator
  ↓
Risk Engine + News + Session + Spread Filters
  ↓
Final Recommendation Builder
  ↓
Signal Store
  ↓
Outcome Validator
  ↓
Performance Metrics + Dashboard + Replay
```

## Implementation Order
Implement the markdown task files in numerical order. After each task:

1. Build the solution.
2. Run existing tests.
3. Add or update tests for the new behavior.
4. Verify database migration/scripts.
5. Verify dashboard/API compatibility.
6. Add a short implementation note in `docs/implementation-progress.md`.

## Naming Requirements
Use clear names. Suggested service names:

- `SignalOutcomeValidator`
- `SignalPerformanceService`
- `ModelPerformanceTracker`
- `DynamicModelWeightService`
- `MarketRegimeDetector`
- `EntryPlanScoringEngine`
- `MultiTimeframeConfirmationService`
- `EconomicNewsFilter`
- `SignalReplayService`
- `WalkForwardBacktestService`
- `ThresholdOptimizationService`

## Final Acceptance Criteria
The system is complete when the dashboard can show:

- Current signal with confidence and grade
- Entry, SL, TP, R:R
- Model votes and dynamic weights
- Indicator summary
- Market regime
- Multi-timeframe alignment
- News/spread/session/risk filters
- Blocked reasons
- Past signal outcomes
- Model-by-model win rate/precision
- Replay/debug view for any past signal
- Backtest and optimization results
