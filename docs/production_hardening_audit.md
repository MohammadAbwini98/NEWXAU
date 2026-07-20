# Production Hardening Audit

## Wiring Trace

```text
Market Data
  -> DataEngine cleaning/aggregation
  -> IndicatorEngine
  -> MarketRegimeDetector
  -> ModelEnsembleEngine
  -> DynamicModelWeightService
  -> MultiTimeframeConfirmationService
  -> EconomicNewsFilter
  -> StrategyBrain
  -> EntrySlTpEngine
  -> RiskEngine
  -> RecommendationBuilder
  -> Storage/PostgreSQL
  -> Dashboard API/UI
  -> SignalOutcomeValidator
  -> ModelPerformanceTracker
```

## Issues

Module: News filter
Current status: MVP manual/mock-capable.
Problem: Provider mode is not explicit enough, real provider has no production-ready fetch boundary, and events are not consistently persisted.
Production impact: Signals can be blocked by manual events, but production users cannot audit provider source or sync status deeply enough.
Recommended fix: Add provider abstraction, config-driven mode, event IDs, persistence hooks, provider health, and signal news snapshots.
Files affected: `config.py`, `news_filter.py`, `pipeline.py`, `api.py`, `storage.py`, `dashboard_static/index.html`.
Priority: Critical

Module: Walk-forward backtesting
Current status: Strategy-only MVP.
Problem: Reports are held in memory and no structured report folder is created.
Production impact: Backtests cannot be audited or shared reliably.
Recommended fix: Save `summary.json`, `folds.csv`, `trades.csv`, `model_metrics.csv`, `strategy_metrics.csv`, and `recommendations.md`.
Files affected: `walk_forward.py`, `api.py`, `docs/`.
Priority: High

Module: Threshold optimization
Current status: Simple grid scorer with in-memory profiles.
Problem: Active thresholds are not loaded by StrategyBrain, versioning is light, rollback is minimal, and train/validation/test scores are not separated.
Production impact: Optimized settings cannot safely control live decisions.
Recommended fix: Add threshold profile service, active profile loading, versioning, rollback, split metrics, and warnings.
Files affected: `optimization.py`, `strategy_brain.py`, `risk_engine.py`, `pipeline.py`, `api.py`, `db/schema.sql`.
Priority: Critical

Module: Signal validation
Current status: Functional canonical outcomes.
Problem: Timeline output is limited and `CANCELLED`/`UNKNOWN` are not first-class final outcomes.
Production impact: Replay and post-trade audit lack full event sequence.
Recommended fix: Add validation timeline, outcome counts, validation latency, and explicit cancellation/unknown support.
Files affected: `outcome_validator.py`, `storage.py`, `api.py`, `dashboard_static/index.html`.
Priority: High

Module: Model performance
Current status: Model metrics are calculated in memory.
Problem: Rolling windows and breakdowns by regime/session/timeframe are partial, and model_prediction_outcomes are not persisted by PostgreSQL.
Production impact: Dynamic weighting can be influenced by incomplete historical model evidence.
Recommended fix: Add rolling window queries, DB persistence methods, and richer metrics DTOs.
Files affected: `performance.py`, `storage.py`, `pipeline.py`, `api.py`.
Priority: High

Module: Dynamic model weighting
Current status: Effective weights with reasons and basic safeguards.
Problem: Weight profiles are not versioned/rollback-capable, changes are not bounded gradually, and DB persistence is missing.
Production impact: A single update can move weights too far and cannot be safely reverted.
Recommended fix: Add versioned profiles, max change per update, active profile, rollback endpoint, and history persistence.
Files affected: `dynamic_weights.py`, `storage.py`, `api.py`, `dashboard_static/index.html`.
Priority: Critical

Module: Entry/SL/TP plan scoring
Current status: Multiple candidate plans with scoring.
Problem: Candidate types do not exactly match production names, no explicit `invalid_if_price_reaches` or `plan_expiry`, and no pipeline-level block if no plan passes.
Production impact: Some invalid plans may remain explainable but not strictly blocked with production statuses.
Recommended fix: Add production candidate aliases, expiry/invalid fields, and block statuses for no valid entry/low R:R/SL width.
Files affected: `contracts.py`, `trade_plan_engine.py`, `pipeline.py`, `dashboard_static/index.html`.
Priority: High

Module: Market regime detection
Current status: Deterministic evidence-based MVP.
Problem: ATR percentile, Bollinger width, body/range ratio, support/resistance proximity, and volume spike evidence are limited.
Production impact: Regime labels can be correct in obvious cases but weak in edge cases.
Recommended fix: Add evidence scores for volatility percentile, directional consistency, candle body ratio, volume spike, and reversal zone.
Files affected: `market_regime.py`, `pipeline.py`, `dashboard_static/index.html`.
Priority: Medium

Module: Multi-timeframe confirmation
Current status: Alignment score and timeframe roles.
Problem: Matrix lacks full trend/momentum/volatility/support/resistance fields.
Production impact: Dashboard shows alignment but not enough higher-timeframe evidence.
Recommended fix: Expand matrix fields and add explicit supports_signal/blocking_signal flags.
Files affected: `multi_timeframe.py`, `dashboard_static/index.html`.
Priority: Medium

Module: Dashboard
Current status: Broad visibility panels.
Problem: Some production-hardening data appears in compact tables rather than drill-down views; some missing values are still terse.
Production impact: Usable, but not yet fully audit-friendly for live review.
Recommended fix: Add explicit provider modes, profile versions, validation counts, report links, and clearer missing-value text.
Files affected: `dashboard_static/index.html`, `api.py`.
Priority: Medium

Module: Production monitoring
Current status: Health service with candle freshness and basic events.
Problem: Logs are not centralized; database write failures, provider failures, strategy latency, notification failures, backtest/optimization status are partial.
Production impact: Critical failures can be missed outside the dashboard.
Recommended fix: Add structured production logger, component health categories, and record events for signal/blocked/validation/weights/news/database jobs.
Files affected: `health.py`, `storage.py`, `pipeline.py`, `api.py`.
Priority: High

Module: Database persistence
Current status: PostgreSQL signal persistence active in `newxau` schema.
Problem: New hardening entities need migrations and some storage methods remain in-memory only.
Production impact: Some historical audit data may disappear across restarts.
Recommended fix: Add production hardening migration and PostgreSQL persistence for hardening tables.
Files affected: `db/schema.sql`, new migration, `storage.py`.
Priority: Critical

Module: Tests
Current status: 38 deterministic tests.
Problem: Production hardening tests for reports, rollback, provider modes, and DB initialization are missing.
Production impact: Critical production behaviors could regress silently.
Recommended fix: Add tests for provider mode, stale data health, threshold rollback, bounded weights, report generation, and API DTOs.
Files affected: `tests/`.
Priority: High
