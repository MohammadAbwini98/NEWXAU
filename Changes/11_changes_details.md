# 11 - Implementation Changes Details

Date: 2026-06-07

This document records the latest implementation upgrades requested after the initial phase-by-phase build.

## Scope Completed

All requested follow-up points were implemented:

1. Strict PostgreSQL read path for signal history endpoints
2. Production scheduler lock and retry policy
3. Per-model performance tracking with automatic dynamic weight updates using backtest/paper outcomes

---

## 1) Strict PostgreSQL Read Path

### What changed

- Added storage-level read APIs used by endpoints instead of direct in-memory lists.
- PostgreSQL storage now reads history and detail directly from `trade_recommendations` (JSON payloads in `raw_json`).
- Latest recommendation/model votes/indicator snapshot/risk check can be reconstructed from DB to survive process restarts.

### Files

- `src/gold_signal_system/storage.py`
- `src/gold_signal_system/api.py`

### Endpoint impact

- `GET /api/signals/history` now calls storage backend read method.
- `GET /api/signals/{id}` now calls storage backend read method.

When `POSTGRES_DSN` is configured and DB is reachable, these reads are strict DB reads.

---

## 2) Scheduler Lock + Retry Policy

### What changed

- Added cycle-execution lock to prevent overlapping cycle runs between background scheduler and manual trigger.
- Added retry + exponential backoff for live cycle execution on transient failures.
- Background runner and manual run endpoint now both use the same guarded execution path.

### Files

- `src/gold_signal_system/config.py`
- `src/gold_signal_system/api.py`

### New runtime settings

- `LIVE_CYCLE_RETRY_ATTEMPTS` (default: `3`)
- `LIVE_CYCLE_RETRY_BACKOFF_SECONDS` (default: `2`)

---

## 3) Model Performance Tracking + Dynamic Weights

### What changed

- Added model performance tracker to compute:
  - BUY precision
  - SELL precision
  - HOLD accuracy
  - Win rate (when model agrees with final signal)
  - Profit factor contribution
  - False signal rate
  - Average return
  - Drift score
- Added dynamic weight suggestion logic from tracked metrics.
- Backtesting outcomes now feed tracker automatically per trade.
- Paper-trading tracked outcomes now feed tracker and persist outcomes.
- Adaptive weights are persisted in system settings.

### Files

- `src/gold_signal_system/performance.py`
- `src/gold_signal_system/pipeline.py`
- `src/gold_signal_system/backtesting.py`
- `src/gold_signal_system/paper_trading.py`
- `src/gold_signal_system/storage.py`
- `src/gold_signal_system/api.py`

### New runtime settings

- `ENABLE_DYNAMIC_MODEL_WEIGHTS` (default: `1`)
- `MIN_OBSERVATIONS_FOR_REWEIGHT` (default: `10`)

---

## Additional Production Hardening Included

- Data provider abstraction supports `synthetic`, `csv`, `capitalcom`.
- Background event bus drives websocket realtime push.
- Dashboard switched to websocket-driven updates.
- README updated with runtime modes and environment configuration.

---

## Validation Summary

- Unit tests pass after these changes.
- End-to-end cycle execution still works.
- API app initialization works.

