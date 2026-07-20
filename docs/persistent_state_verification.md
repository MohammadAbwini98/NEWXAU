# Persistent Runtime State Verification

## What Was Memory-Only Before

- Optimization runs, candidates, profiles, and rollback stack.
- Dashboard model weight and risk-limit settings.
- Dynamic model weight history, versions, and latest effective weights.
- Health events, model latency counters, and failure counters.
- Running backtest jobs could remain stuck as `RUNNING` after restart.

## What Is Now Persisted

- Optimization runs and candidates.
- Optimization profiles and profile versions.
- Optimization rollback records.
- Dashboard settings through `system_settings`.
- Active dynamic model weights, versions, and adjustment records.
- Warning/critical health events and service snapshots.
- Interrupted backtest/walk-forward job status.

## Runtime-Only By Design

- WebSocket subscriber queues.
- Latest live websocket price tick/status.
- Dashboard selected tab, selected row, frontend logs, and loaded replay object.
- Capital.com websocket task object.
- Temporary walk-forward service process-local objects while a job is actively executing.

## Database Tables Added Or Extended

Migration: `db/005_persistent_runtime_state.sql`

- `optimization_runs`
- `optimization_candidates`
- `optimization_profiles`
- `optimization_profile_versions`
- `optimization_rollbacks`
- `system_settings`
- `model_weight_profiles`
- `model_weight_versions`
- `model_weight_adjustments`
- `health_events`
- `service_health_snapshots`

## Startup Reload Behavior

Startup now calls `bootstrap_runtime_state(...)`, which:

- marks stale `RUNNING` backtest/walk-forward jobs as `INTERRUPTED`
- imports backtest report metadata
- reloads dashboard settings
- reloads active model weights
- creates a default model weight profile if none exists
- reloads optimization profiles and runs
- loads latest health snapshot
- writes startup health snapshot

Startup logs include:

```text
Loaded active optimization profile: X
Loaded optimization runs: N
Loaded active model weight profile: X
Loaded system settings: N
Loaded health snapshots: N
Live price state: in-memory only
Marked interrupted jobs: N
```

## Dashboard Reload Behavior

- Optimization view shows a clear empty state if no runs exist.
- Model weight history reports when default weights are being used.
- Health view shows persisted snapshot state.
- Price pill waits for the live websocket tick after startup; stale persisted ticks are not shown.
- Settings saves return `updated_at` and `source`.

## Endpoints Changed

- `GET /api/optimization/runs`
- `GET /api/optimization/runs/{run_id}`
- `GET /api/optimization/runs/{run_id}/candidates`
- `GET /api/strategy/profiles/active`
- `POST /api/settings/model-weights`
- `POST /api/settings/risk-limits`
- `GET /api/models/weights/current`
- `GET /api/models/weights/history`
- `POST /api/models/weights/recalculate`
- `GET /api/system/health`
- `GET /api/system/health/events`
- `GET /api/price/latest`

## Tests Added

File: `tests/test_persistent_runtime_state.py`

Coverage includes:

- optimization runs and profiles reloading from storage
- dashboard settings saving to storage
- active model weight state persistence
- health event/snapshot persistence
- latest market state is not reloaded as live price
- running backtest jobs marked interrupted
- startup bootstrap reload summary
- dashboard empty-state text

## Explicit Confirmations

- `/api/optimization/runs` reads durable storage.
- Optimization profiles reload through `ThresholdOptimizationService.reload_from_storage()`.
- Dashboard model weight changes save as `model_weights.active`.
- Dashboard risk limit changes save as `risk_limits.active`.
- Dynamic model weights reload latest effective profile after restart.
- Health events/snapshots are visible after restart through storage-backed endpoints.
- Running backtest/walk-forward jobs are not left stuck in `RUNNING`.
- Runtime-only states, including live websocket price, are documented as intentionally non-persistent.
- Startup logs show what was reloaded.

## Known Limitations

- Optimization execution remains synchronous.
- Health snapshot retention is basic and can be expanded with configurable retention windows.
- Dashboard browser-local state is intentionally not persisted.
