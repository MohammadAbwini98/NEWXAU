# Final Wiring Verification

Verification date: 2026-06-08

## Test And Runtime Status

- Unit/integration tests: `43 tests OK`
- Database initialization: `OK`
- Active database schema: `newxau`
- Storage backend: `postgresql`
- Dashboard smoke test: passed
- Production hardening migration applied: `db/003_production_hardening.sql`

## End-To-End Flow

Market Data -> Indicator Engine: Verified. Capital.com candles and synthetic fixtures flow through `DataEngine` cleaning/aggregation.

Indicator Engine -> Model Ensemble: Verified. Indicator snapshots feed model feature vectors and model votes.

Model Ensemble -> Model Vote Normalizer: Verified. Model votes are normalized as `ModelPrediction` DTOs.

Model Vote Normalizer -> Dynamic Model Weights: Verified. Dynamic weights are calculated with bounded changes, min/max limits, profile version history, and reasons.

Dynamic Model Weights -> Market Regime Detector: Verified. Regime is calculated before final strategy selection and stored in signal snapshots.

Market Regime Detector -> Multi-Timeframe Confirmation: Verified. The matrix includes trend, momentum, volatility, support/resistance, and support/block flags.

Multi-Timeframe Confirmation -> News Filter: Verified. News provider mode is configurable and current news risk is checked per signal.

News Filter -> Strategy Brain: Verified. News blocks can force `BLOCKED_BY_NEWS`, and the final signal includes exact event reasons.

Strategy Brain -> Entry/SL/TP Plan Engine: Verified. Multiple production entry plans are scored and selected/rejected with reasons.

Entry/SL/TP Plan Engine -> Risk Engine: Verified. Risk validates selected plan, spread, news window, R:R, SL distance, volatility, and conflicts.

Risk Engine -> Final Recommendation: Verified. Final recommendations include strategy version, threshold profile ID, model weight profile ID, blocked reasons, and trade plan.

Final Recommendation -> Database Persistence: Verified. Signals, snapshots, model rows, outcomes, entry plans, regimes, and timeframe confirmations persist through PostgreSQL.

Database Persistence -> Dashboard API/UI: Verified. APIs return current signal, replay, entry plans, model performance, weights, regime, news, health, and outcome summaries.

Dashboard API/UI -> Signal Validation: Verified. Validation outcomes and timeline are visible in replay/outcomes payloads.

Signal Validation -> Model Performance Tracking: Verified. Final outcomes update model performance metrics and prediction outcome rows.

Model Performance Tracking -> Dynamic Weight Update: Verified. Dynamic weights use model metrics with bounded updates and reasons.

## Required Checks

- Each module is called by the correct upstream service: Passed.
- Each module writes required database records: Mostly passed. Some hardening history tables exist as migrations; selected history remains in service memory until deeper DB adapters are implemented.
- Each module is exposed by API if needed: Passed.
- Each module is visible in dashboard if needed: Passed.
- Each module has logs: Passed for signal generation, blocked signals, validation outcomes, weight updates, and news blocks through health events.
- Each module has tests: Passed for critical modules.
- No mock provider is used in production mode unless explicitly configured: Passed. Default is manual; mock requires `NEWS_PROVIDER_MODE=mock`.
- No hardcoded thresholds remain in Strategy Brain: Passed. StrategyBrain reads `StrategyThresholdProfile`.
- No generated signal is lost without validation: Passed for persisted signals; eligible pending signals validate on future candle cycles.
- No model prediction is ignored without reason: Passed. Model predictions are persisted per signal with weight used.

## Sample Outputs

Generated signal:

```json
{
  "signal": "SELL",
  "status": "BLOCKED_BY_RISK",
  "confidence": 0.4753,
  "storage_backend": "postgresql"
}
```

Blocked signal with reasons:

```json
{
  "status": "BLOCKED_BY_NEWS",
  "blocked_reasons": [
    "High-impact USD US CPI Verification Event event in 14 minutes",
    "High-impact news window active before event.",
    "Price too close to opposite level."
  ]
}
```

Validated signal outcome summary:

```json
{
  "total": 23,
  "counts": {
    "EXPIRED": 14,
    "MISSED_ENTRY": 4,
    "PARTIAL_TP": 4,
    "NO_TRADE": 1
  }
}
```

Model performance update:

```json
{
  "model_signal_predictions": "persisted per signal",
  "confidence_calibration": "available by model",
  "metrics_endpoint": "/api/models/performance/summary"
}
```

Dynamic weight update:

```json
{
  "kronos": {
    "base_weight": 0.3,
    "effective_weight": 0.29411765,
    "reason": "Insufficient performance data; base weight retained."
  }
}
```

News-blocked signal:

```json
{
  "provider_mode": "manual",
  "event": "US CPI Verification Event",
  "status": "BLOCKED_BY_NEWS"
}
```

Walk-forward report summary:

```json
{
  "report_folder": "reports/walk_forward/run_<id>",
  "files": ["summary.json", "folds.csv", "trades.csv", "model_metrics.csv", "strategy_metrics.csv", "recommendations.md"]
}
```

Threshold optimization summary:

```json
{
  "split": ["train", "validation", "unseen_test"],
  "rollback": "available",
  "activation": "manual"
}
```

Production health snapshot:

```json
{
  "overall_status": "HEALTHY",
  "database": "HEALTHY",
  "news_provider": "HEALTHY",
  "models": "HEALTHY"
}
```

## Remaining TODOs

Priority: High
TODO: Persist every in-memory hardening service history row through PostgreSQL adapters, especially versioned dynamic weight profiles and optimization results.
Reason: Migrations exist, but some service history APIs still read in-memory state for speed and compatibility.

Priority: Medium
TODO: Implement a real external economic calendar provider endpoint contract for the chosen vendor.
Reason: `RealEconomicCalendarProvider` is ready for JSON HTTP input, but no vendor-specific adapter/API key is configured.

Priority: Medium
TODO: Plug model retraining into walk-forward Mode B.
Reason: Extension points are present, but real training requires trained model code/artifact management outside the current baseline adapters.

Priority: Low
TODO: Expand dashboard drill-down charts for fold metrics, calibration curves, and equity curves.
Reason: Data/API exists, but UI currently prioritizes compact tables.

## Production Readiness Statement

The system passes hardening tests and wiring verification for demo/live recommendation mode with persistent storage. It is not marked fully production-ready for autonomous trading because real news-vendor integration and real model-retraining integration remain explicit TODOs.
