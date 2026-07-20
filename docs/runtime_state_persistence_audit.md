# Runtime State Persistence Audit

## Production Rule

Runtime-only state is acceptable. Configuration, profiles, optimization history, adaptive model weights, user dashboard settings, and important health records must persist.

## Optimization Runs And Profiles

Component: Threshold optimization service

Current memory fields: `optimization_service.runs`, `optimization_service.candidates`, `optimization_service.profiles`, `rollback_stack`

Current endpoint impact: `/api/optimization/runs`, `/api/optimization/runs/{id}`, `/api/optimization/runs/{id}/candidates`, `/api/strategy/profiles/active`

Should persist: yes

Classification: `PERSIST_REQUIRED`

Persistence target: PostgreSQL

Reload behavior after restart: startup reload reads profiles and runs from storage; default profile is created if none exists.

Implementation status: persisted through storage methods and service reload.

Files affected: `db/005_persistent_runtime_state.sql`, `src/gold_signal_system/storage.py`, `src/gold_signal_system/optimization.py`, `src/gold_signal_system/startup_state.py`, `src/gold_signal_system/api.py`

## Dashboard Settings

Component: dashboard settings API

Current memory fields: `system.storage.system_settings["model_weights"]`, `system.storage.system_settings["risk_limits"]`

Current endpoint impact: `/api/settings/model-weights`, `/api/settings/risk-limits`

Should persist: yes

Classification: `PERSIST_REQUIRED`

Persistence target: PostgreSQL `system_settings`

Reload behavior after restart: model weights and risk limits are applied during `GoldSignalSystem` initialization and startup bootstrap.

Implementation status: persisted with `source`, `updated_by`, and `updated_at`.

Files affected: `db/005_persistent_runtime_state.sql`, `src/gold_signal_system/storage.py`, `src/gold_signal_system/pipeline.py`, `src/gold_signal_system/api.py`

## Dynamic Model Weights

Component: dynamic model weight service

Current memory fields: `history`, `profile_versions`, `_last_effective_weights`

Current endpoint impact: `/api/models/weights/current`, `/api/models/weights/history`, signal generation

Should persist: yes

Classification: `PERSIST_REQUIRED`

Persistence target: PostgreSQL

Reload behavior after restart: latest active weights are loaded into `ModelEnsembleEngine`; profile versions are loaded into the dynamic weight service.

Implementation status: active weights, versions, and adjustment records are persisted.

Files affected: `db/005_persistent_runtime_state.sql`, `src/gold_signal_system/storage.py`, `src/gold_signal_system/pipeline.py`, `src/gold_signal_system/api.py`

## Health Events And Snapshots

Component: system health service

Current memory fields: `events`, `model_latencies`, `model_failures`

Current endpoint impact: `/api/system/health`, `/api/system/health/events`

Should persist: yes for warning/critical events and snapshots; no for every small runtime counter mutation.

Classification: `PERSIST_REQUIRED`

Persistence target: PostgreSQL

Reload behavior after restart: latest persisted snapshot is shown with runtime health; warning/critical events remain queryable.

Implementation status: persisted with retention cleanup for snapshots.

Files affected: `db/005_persistent_runtime_state.sql`, `src/gold_signal_system/storage.py`, `src/gold_signal_system/health.py`, `src/gold_signal_system/api.py`

## Live Market Price

Component: Capital.com live price tick/status

Current memory fields: `latest_price_tick`, `latest_price_stream_status`

Current endpoint impact: `/api/price/latest`

Should persist: no

Classification: `RUNTIME_ONLY`

Persistence target: process memory only

Reload behavior after restart: dashboard waits for a new live websocket tick. Stale saved prices are not shown and are not used for execution.

Implementation status: websocket ticks update in-memory state and are broadcast through `/ws/events`; database migration `008_live_price_memory_only.sql` drops the old `latest_market_state` table.

Files affected: `db/008_live_price_memory_only.sql`, `src/gold_signal_system/storage.py`, `src/gold_signal_system/api.py`, `src/gold_signal_system/startup_state.py`

## Backtest Running Jobs

Component: backtest and walk-forward execution

Current memory fields: temporary service `runs`, `windows`, `signals`

Current endpoint impact: `/api/backtests`, dashboard Backtesting view

Should persist: completed history yes; active execution memory can remain runtime-only.

Classification: `PERSIST_REQUIRED` for durable job status, `RUNTIME_ONLY` for active process objects.

Persistence target: PostgreSQL

Reload behavior after restart: startup marks `RUNNING` jobs as `INTERRUPTED`.

Implementation status: persisted and interrupted jobs are cleaned up by startup bootstrap.

Files affected: `src/gold_signal_system/storage.py`, `src/gold_signal_system/startup_state.py`

## WebSocket Event Bus

Component: event bus subscriber queues

Current memory fields: subscriber queues

Current endpoint impact: `/ws/events`

Should persist: no

Classification: `RUNTIME_ONLY`

Persistence target: runtime only

Reload behavior after restart: clients reconnect and receive new live events.

Implementation status: intentionally not persisted.

Files affected: none

## Dashboard Browser State

Component: browser UI state

Current memory fields: selected tab, selected row, frontend logs, loaded replay object

Current endpoint impact: browser only

Should persist: no, except optional frontend local storage if desired later.

Classification: `RUNTIME_ONLY`

Persistence target: runtime only

Reload behavior after restart/page refresh: dashboard refetches durable API data.

Implementation status: intentionally not persisted.

Files affected: `src/gold_signal_system/dashboard_static/index.html`
