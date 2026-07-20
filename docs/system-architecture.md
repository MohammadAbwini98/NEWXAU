# System Architecture

The current signal flow is:

```text
Capital.com candles / synthetic candles
  -> DataEngine cleaning and aggregation
  -> IndicatorEngine
  -> MarketRegimeDetector
  -> ModelEnsembleEngine
  -> DynamicModelWeightService
  -> MultiTimeframeConfirmationService
  -> StrategyBrain
  -> EntrySlTpEngine candidate scoring
  -> RiskEngine + EconomicNewsFilter + SystemHealthService
  -> RecommendationBuilder
  -> Signal snapshots, model prediction rows, entry plans, outcomes
  -> Dashboard, replay, backtests, optimization
```

The dashboard remains the project entry point. Running `python scripts/run_api.py` starts the API, replaces any existing server on port `8000`, and opens the dashboard.

Critical system health blocks directional recommendations with `BLOCKED_BY_SYSTEM_HEALTH`. Live quote ticks update the dashboard price independently from closed-candle signal generation.
