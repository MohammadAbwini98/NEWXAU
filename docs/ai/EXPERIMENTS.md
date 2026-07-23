# Experiment Register

## EXP-2026-07-21-DQ-001 - Data-quality shadow gate

- Hypothesis: a fail-closed quality gate can prevent stale/corrupt candles from reaching model inference without changing default recommendation behavior.
- Dataset and split: deterministic synthetic XAUUSD candles; anomaly unit fixtures and a stale 80-candle 5m series. No train/test split because this is a safety-contract experiment, not a performance estimate.
- Features and models: existing feature pipeline and active model roster; blocked candidate uses deterministic HOLD abstention and invokes no adapter.
- Configuration: gate off for control/default behavior; candidate uses `ENABLE_DATA_QUALITY_GATE=1` with score 85, missing ratio 2%, outlier ratio 1%, and freshness multiplier 2.5.
- Costs: not applicable to the safety-contract assertion.
- Metrics: inference invocation count, final signal, gate state, bucket completeness, focused regression tests, and cycle latency.
- Result: stale candidate returned HOLD, `gate_status=BLOCKED`, all versions were `DATA_QUALITY_ABSTAIN`, and mocked `run_models` was not called. Default remains `MONITOR_ONLY`. Focused combined validation passed.
- Latency: baseline three-cycle mean 3537.10 ms; candidate-code mean 4500.47 ms. The candidate warm trace attributed 118 ms to validation plus aggregation and 2681.827 ms to model inference. Run-to-run model/cold-start variance prevents an improvement claim.
- Decision: keep implementation, do not promote the gate by default. Collect shadow block-rate and false-block evidence before activation.
- Rollback: set `ENABLE_DATA_QUALITY_GATE=0` or remove it. No database rollback.

## EXP-2026-07-21-BT-001 - Trading-cost accounting fixture

- Hypothesis: applying declared spread, round-trip slippage, and commission produces more conservative and internally consistent net R.
- Dataset and split: deterministic one-trade BUY fixture; entry 100, stop 99, TP1 101. No statistical split.
- Features and models: not applicable; direct simulator contract test.
- Configuration: spread 0.20 points, slippage 0.10 points per fill, commission 0.05 R.
- Costs: total cost = `(0.20 + 2 * 0.10) / 1.00 + 0.05 = 0.45 R`.
- Metrics: gross R, cost R, net R.
- Result: gross `1.00 R`, modeled cost `0.45 R`, net `0.55 R`; regression test passed.
- Decision: keep as a backtest correctness fix. Invalidate direct comparisons with reports generated under legacy cost-free accounting until rerun.
- Rollback/comparison mode: explicitly set spread, slippage, and commission to zero and label the output cost-free.
