# Trading Intelligence and Outcome Enhancement Audit

Date: 2026-07-21
Scope: read-only architecture audit plus the smallest P0/P1 reliability corrections
Execution impact: none by default; Capital.com execution remains disabled and demo-only guarded

## Executive Summary

The pipeline is modular and already has strong execution guard rails, deterministic model fallbacks, canonical Jordan session handling, and in-memory storage fallback. The most important reliability gap was upstream of those controls: candle integrity was reported but could not prevent model inference, and partial higher-timeframe buckets could be consumed. Backtest configuration also declared spread and slippage without applying either to outcomes.

This change adds observable data-quality scoring and an opt-in, fail-closed inference gate; filters incomplete derived candles when the gate is enabled; records pipeline stage timings; and makes the legacy backtest deduct configured trading costs. It does not tune strategy thresholds, claim improved profitability, activate execution, or promote any model.

## Baseline

| Item | Observed baseline | Interpretation |
|---|---:|---|
| Focused pipeline/config/session tests | 9 passed, 13 subtests | Existing focused behavior was green before changes. |
| Synthetic 900-candle cycle latency | 5711.97 / 2550.36 / 2348.98 ms; mean 3537.10 ms | Cold start is material; warm model inference dominates. |
| Mock walk-forward, 253 trades | win rate 0.5318; PF 3.2394; max DD 83.0; avg R 0.3933 | Not production evidence: mock models and legacy cost-free accounting. |
| Mock walk-forward, 14 trades | win rate 1.0; PF 28.0006 | Demonstrates sample-size instability, not an edge. |

Historical report source: existing JSON under `reports/walk_forward/`. No historical report was modified.

## Findings and Priority

| Priority | Finding | Evidence | Status |
|---|---|---|---|
| P0 | Data-quality failures could not stop inference. | `DataQualityReport` was returned but not consumed before `run_models`. | Fixed behind `ENABLE_DATA_QUALITY_GATE`, default off. |
| P0 | Backtest spread and slippage settings were unused. | `_simulate_outcome` returned gross R and only commission was subtracted later. | Fixed for the legacy backtest engine. |
| P0 | Execution must remain off/demo-only. | Runtime defaults and Capital execution preflight tests. | Verified unchanged. |
| P1 | Partial 1m-derived HTF buckets could enter indicators/MTF. | Aggregator accepted every bucket regardless of expected source timestamps. | Complete buckets are required when quality gate is enabled; monitoring is always reported. |
| P1 | Cycle latency lacked stage visibility. | Only end-to-end observation was available. | Stage timings added to cycle/API/signal snapshot. |
| P1 | MTF conflict can be overly restrictive. | Any opposite 1h bias blocks, while the message describes a strong conflict. | Audit only; needs ablation before change. |
| P1 | Regime vocabulary omits explicit stale/illiquid/session-transition states. | Current detector focuses on trend/range/chop/volatility/news spike. | Pending evidence-backed design. Data staleness is now handled before inference. |
| P1 | Walk-forward comparability is incomplete. | Existing reports include mock models and were produced before cost-aware legacy simulation. | Rerun required; no promotion claim. |
| P2 | Calibration lacks Brier score and ECE. | Performance tracker uses confidence buckets and directional metrics only. | Pending. |
| P2 | Risk sizing is fixed-fractional only. | No volatility-targeted sizing or conservative Kelly cap. | Pending; should not change without OOS evidence. |
| P2 | Model inference is sequential and dominates warm latency. | Instrumented candidate cycle: model inference 2681.827 ms of 2811.790 ms. | Measure adapters independently before considering safe parallelism. |
| P3 | Stacking/meta-labeling and regime-specific ensemble selection. | No leakage-safe meta-model evaluation exists yet. | Research only. |

## Implemented Changes

### Data-quality contract and gate

Every cycle now reports:

- `quality_score`, `freshness_seconds`, missing/duplicate/outlier/out-of-order counts;
- `spread_status`, `aggregation_status`, `provider_status`, and `blocking_reasons`;
- `gate_status` (`MONITOR_ONLY`, `PASSED`, or `BLOCKED`).

When `ENABLE_DATA_QUALITY_GATE=1` and a hard reason exists, model adapters are not invoked. Deterministic `DATA_QUALITY_ABSTAIN` HOLD votes preserve downstream contracts, existing model weights are retained, risk is marked blocked, and reasons are persisted. Direct historical calls do not receive a wall-clock reference by default, preventing historical candles from being incorrectly labelled stale.

### Complete aggregation

The 1m aggregator can require every expected minute in a target bucket. The pipeline always reports incomplete bucket counts. It filters them from downstream use only when the opt-in gate is enabled, preserving default recommendation behavior until shadow validation is complete.

### Timing telemetry

Cycle responses expose milliseconds for data validation, aggregation, feature/context work, model inference, decision work, pre-persistence total, and total. The signal snapshot stores timings available before persistence.

### Cost-aware legacy backtest

Backtest cycles now receive configured spread for risk evaluation. Net realized R deducts:

`(spread + 2 * slippage) / stop_distance + commission_per_trade`

Reports include gross R, cost R, net R, aggregate modeled cost, assumptions, total evaluated signals, and actual blocked-signal count. Same-candle stop-first behavior remains conservative.

## Configuration and Rollback

Shadow/monitoring is the default. To test fail-closed behavior explicitly:

```env
ENABLE_DATA_QUALITY_GATE=1
DATA_QUALITY_MIN_SCORE=85
DATA_QUALITY_MAX_MISSING_RATIO=0.02
DATA_QUALITY_MAX_OUTLIER_RATIO=0.01
DATA_QUALITY_FRESHNESS_MULTIPLIER=2.5
```

Rollback the gate by removing `ENABLE_DATA_QUALITY_GATE` or setting it to `0`; no schema rollback is needed. To reproduce legacy cost-free backtest assumptions for comparison only, construct `BacktestConfig(spread=0, slippage=0, commission_per_trade=0)` and label the result as cost-free.

## Validation and Promotion Gates

Completed locally with mocks/synthetic data:

- compilation of `src` and tests;
- data-quality anomaly, complete-bucket, pre-inference abstention, default-off, and cost-accounting tests;
- focused pipeline, session, production-hardening, API/dashboard, improvement-service, and Capital execution-safety tests;
- memory validation.

Not completed and required before claiming production readiness:

1. time-ordered out-of-sample rerun using real, versioned market data;
2. walk-forward folds with identical cost assumptions, session segmentation, and leakage checks;
3. calibration metrics (Brier/ECE) and stability across regimes;
4. shadow-mode quality-gate statistics, including block rate and false-block review;
5. sustained paper/demo trading with deterministic reconciliation and zero safety violations.

## Roadmap

1. P0/P1: rerun cost-aware, time-ordered baselines and report trade count, net expectancy, drawdown, PF, calibration, and session/regime slices.
2. P1: ablate the unconditional 1h MTF conflict rule against a strength-aware rule.
3. P1/P2: add explicit stale/illiquid/session-transition context and calibrated abstention thresholds.
4. P2: profile each model adapter and cache only immutable preprocessing; consider bounded parallelism only if thread/process safety is proven.
5. P2/P3: evaluate volatility-targeted sizing, meta-labeling, and regime-aware weighting only behind flags and only after OOS improvement with no drawdown or safety regression.

No profit, robustness, or production-readiness claim is made by this audit.
