# Persist Remaining In-Memory State — Gold Signal System

## Context

The system has improved backtest persistence, but there are still important runtime states that are currently kept in memory.

Current memory-only components reported:

1. **Optimization runs and profiles**
   - `optimization_service.runs`
   - `optimization_service.candidates`
   - `optimization_service.profiles`
   - `rollback_stack`
   - Endpoint affected: `/api/optimization/runs`
   - Meaning: optimization history and proposed profiles can disappear after API restart.

2. **Live price tick state**
   - `latest_price_tick`
   - `latest_price_stream_status`
   - Capital.com websocket task state
   - This is acceptable as runtime state, but latest tick is not persisted.

3. **WebSocket event bus**
   - EventBus subscriber queues and live dashboard events.
   - This is expected to be memory-only and should not persist.

4. **Dashboard browser state**
   - Frontend logs
   - Selected tab
   - Selected backtest row
   - Loaded replay object
   - These reset on page reload.

5. **Health service runtime state**
   - Health events
   - Model latency counters
   - Failure counters
   - Some DB tables exist, but current health service state is still mostly memory.

6. **Dynamic model weight service internal state**
   - `history`
   - `profile_versions`
   - `_last_effective_weights`
   - Some snapshots are saved, but the internal adaptive state is not fully reloaded after restart.

7. **Settings changed from dashboard**
   - `/api/settings/model-weights`
   - `/api/settings/risk-limits`
   - These currently update `system.storage.system_settings` in memory, so manual dashboard changes may not survive restart.

8. **Walk-forward service temporary state**
   - `walk_forward_service.runs/windows/signals`
   - Completed backtests are now persisted and read from DB, so this remaining memory is mostly temporary during execution.

---

## Production Rule

The main production rule is:

```text
Runtime-only state is acceptable.
Configuration, profiles, optimization history, adaptive model weights, and user dashboard settings must persist.
```

---

## Priority Classification

### Must Persist

These should be moved from memory to PostgreSQL or durable JSON files:

```text
1. Optimization runs and profiles
2. Dynamic model weight profiles and history
3. Dashboard settings changes
4. Health events / important failure counters
```

### Can Stay Memory-Only

These are normal runtime/live states:

```text
1. WebSocket event bus subscriber queues
2. Dashboard selected tab / selected row
3. Temporary walk-forward execution state while job is running
4. Capital.com websocket task state
```

### Optional Persistence

These can be persisted if better dashboard recovery is required:

```text
1. latest_price_tick
2. latest_price_stream_status
3. recent frontend logs
4. latest replay object
```

---

# Codex Implementation Prompt

## Main Goal

Review the current system and fix the remaining important memory-only states.

Make all important configuration, profiles, optimization history, dynamic weights, and health records survive API restart.

Do **not** persist things that should naturally be runtime-only, such as WebSocket subscriber queues.

---

# Task 1 — Create State Persistence Audit

Create:

```text
docs/runtime_state_persistence_audit.md
```

For each memory state, classify it as:

```text
PERSIST_REQUIRED
PERSIST_OPTIONAL
RUNTIME_ONLY
```

For each item, include:

```text
Component:
Current memory fields:
Current endpoint impact:
Should persist: yes/no/optional
Persistence target: PostgreSQL / JSON file / local storage / runtime only
Reload behavior after restart:
Implementation status:
Files affected:
```

The audit must clearly explain which states are intentionally runtime-only and which ones must be moved to persistent storage.

---

# Task 2 — Persist Optimization Runs and Profiles

Move optimization service state from memory-only to PostgreSQL.

Persist:

```text
optimization_runs
optimization_candidates
optimization_profiles
optimization_profile_versions
optimization_rollbacks
```

Required behavior:

1. `/api/optimization/runs` must load from PostgreSQL.
2. Optimization history must survive API restart.
3. Proposed profiles must survive API restart.
4. Active profile must be reloadable on startup.
5. Rollback stack must be persisted as version history, not only memory stack.
6. Dashboard must show the same optimization data after restart.

Suggested tables:

```text
optimization_runs
- id
- run_id
- status
- started_at
- completed_at
- config_json
- metrics_json
- selected_profile_id
- error_message
- created_at
- updated_at

optimization_candidates
- id
- run_id
- candidate_id
- parameters_json
- train_metrics_json
- validation_metrics_json
- test_metrics_json
- score
- rank
- created_at

optimization_profiles
- id
- profile_id
- name
- is_active
- parameters_json
- source_run_id
- created_at
- updated_at

optimization_profile_versions
- id
- profile_id
- version_number
- parameters_json
- change_reason
- created_at
```

Implementation requirements:

- Add safe PostgreSQL migrations.
- Add repository/storage layer functions.
- Update service to read/write from DB.
- Keep in-memory cache only as a runtime optimization, not as source of truth.
- On startup, reload active optimization profile and recent runs.
- Ensure dashboard endpoints read from durable storage.

---

# Task 3 — Persist Dashboard Settings

Fix these endpoints:

```text
/api/settings/model-weights
/api/settings/risk-limits
```

Current issue:

They update `system.storage.system_settings` in memory.

Required behavior:

1. Settings must save to PostgreSQL.
2. Settings must reload on API startup.
3. Settings must expose `updated_at` and `source`.
4. Dashboard should show save success/failure.
5. No manual dashboard setting should disappear after restart.

Suggested table:

```text
system_settings
- id
- setting_key
- setting_value_json
- setting_group
- updated_by
- updated_at
- created_at
```

Examples:

```text
setting_key = model_weights.active
setting_key = risk_limits.active
setting_key = thresholds.active_profile
setting_key = news.provider_mode
```

Implementation requirements:

- Add read/write setting repository.
- Replace memory-only setting updates with DB persistence.
- Add validation for model weights and risk limits before saving.
- Reload settings into runtime services on API startup.
- Add clear dashboard feedback when save fails.

---

# Task 4 — Persist Dynamic Model Weight State

The dynamic model weight service must persist and reload:

```text
history
profile_versions
_last_effective_weights
```

Required behavior:

1. Current active weights survive restart.
2. Weight history survives restart.
3. Weight profile versions survive restart.
4. Weight adjustment reasons are stored.
5. Service reloads latest active profile on startup.
6. Dashboard shows current weights and history after restart.

Suggested tables:

```text
model_weight_profiles
- id
- profile_id
- name
- is_active
- weights_json
- created_at
- updated_at

model_weight_versions
- id
- profile_id
- version_number
- weights_json
- reason
- metrics_snapshot_json
- created_at

model_weight_adjustments
- id
- adjustment_id
- profile_id
- model_name
- old_weight
- new_weight
- reason
- metrics_window_json
- created_at
```

Rules:

- Never allow one model to dominate completely.
- Respect min/max weights.
- Weight changes must be gradual.
- Every change must have a reason.
- Reload latest effective weights on startup.
- If no persisted weights exist, create and persist a default profile.

---

# Task 5 — Persist Health Events and Important Counters

Health service memory state should be partially persisted.

Persist:

```text
health_events
model_latency_snapshots
failure_counters
service_status_snapshots
```

Do not persist every tiny runtime event forever. Use retention rules.

Suggested tables:

```text
health_events
- id
- event_id
- severity: INFO / WARNING / CRITICAL
- component
- message
- details_json
- created_at

service_health_snapshots
- id
- component
- status
- latency_ms
- failure_count
- details_json
- created_at
```

Required behavior:

1. Dashboard shows latest health after restart.
2. Critical events survive restart.
3. Health history can be queried.
4. Apply retention cleanup, for example keep latest 7 or 30 days.
5. Runtime counters may still exist in memory, but periodic snapshots must persist.

Implementation requirements:

- Store health events when severity is WARNING or CRITICAL.
- Store periodic snapshots for important services.
- Add endpoint support if missing.
- Update dashboard health panels to show latest persisted state plus live runtime state.

---

# Task 6 — Optional Latest Price Tick Persistence

Live price tick state may remain runtime-only, but improve dashboard recovery by persisting the latest tick/status.

Persist only the latest snapshot, not every tick.

Suggested table:

```text
latest_market_state
- instrument
- bid
- ask
- mid
- spread
- timestamp
- stream_status
- source
- updated_at
```

Required behavior:

1. On API startup, dashboard can show last known tick with a clear stale warning.
2. If tick is older than the allowed threshold, show:

```text
STALE_PRICE_DATA
```

3. Do not treat stale price as live price.
4. Do not use stale tick for live recommendation execution.
5. Live recommendations must require fresh stream/candle data.

Implementation requirements:

- Persist latest XAUUSD market state periodically or on tick update.
- Reload last known market state on startup.
- Dashboard should display stale/fresh state clearly.
- Add config for stale threshold, for example 30–120 seconds.

---

# Task 7 — Walk-Forward Running Job Recovery

Completed runs are now persisted. Temporary execution state can stay in memory.

However, after API restart:

1. Any `RUNNING` walk-forward/backtest job in DB should be marked:

```text
INTERRUPTED
```

or:

```text
FAILED_RESTARTED
```

2. Dashboard should show:

```text
The previous run was interrupted by API restart.
```

3. Do not leave jobs permanently stuck in `RUNNING`.

Implementation requirements:

- On startup, scan backtest/walk-forward run tables for `RUNNING` jobs.
- Mark them interrupted with reason.
- Add timestamp and error message.
- Dashboard should show this as a clear state, not as a silent failure.

---

# Task 8 — Startup Reload Service

Create a startup reload process that loads durable state from PostgreSQL.

On API startup, reload:

```text
active optimization profile
optimization run history
active model weight profile
model weight history
system settings
latest health snapshot
latest market state snapshot
backtest/walk-forward completed runs
```

Startup logs should clearly show:

```text
Loaded active optimization profile: X
Loaded optimization runs: N
Loaded active model weight profile: X
Loaded system settings: N
Loaded health snapshots: N
Loaded latest market state for XAUUSD
Marked interrupted jobs: N
```

Implementation requirements:

- Create a dedicated startup/bootstrap service.
- Ensure service startup order is correct.
- Do not let Strategy Brain start with empty/default config if persisted config exists.
- If reload fails, log a CRITICAL health event.
- Provide fallback only when explicitly safe.

---

# Task 9 — Dashboard Empty/Reload States

Update dashboard to avoid misleading `N/A` values.

For each module, show clear empty/reload states.

## Optimization

If no optimization exists:

```text
No optimization run has been executed yet.
Run threshold optimization to generate candidate profiles.
```

## Model Weights

If no adaptive history exists:

```text
Using default model weights. No adaptive updates yet.
```

## Health

If no health snapshot exists:

```text
No persisted health snapshot yet. Runtime health will appear after system starts collecting metrics.
```

## Price

If latest persisted tick is stale:

```text
Last known price is stale. Waiting for live stream.
```

Required dashboard behavior:

- Do not show confusing `N/A` values.
- Show whether data is live, persisted, stale, or unavailable.
- Refresh panels after settings changes.
- Confirm saved settings survive reload.

---

# Task 10 — Tests

Add tests for:

```text
Optimization runs survive restart
Optimization profiles survive restart
Dashboard settings survive restart
Model weight active profile survives restart
Model weight history survives restart
Health events persist
Latest market state reloads as stale if old
RUNNING walk-forward jobs are marked interrupted after restart
/api/optimization/runs loads from DB
/api/settings/model-weights saves to DB
/api/settings/risk-limits saves to DB
Startup reload service loads persisted state
Dashboard shows proper empty states instead of N/A
```

Testing guidance:

- Use deterministic tests.
- Simulate API restart by creating records, reinitializing services, then verifying state reload.
- Test both default/no-data state and persisted-data state.
- Ensure runtime-only state is not incorrectly persisted.

---

# Task 11 — Verification Document

Create:

```text
docs/persistent_state_verification.md
```

Include:

```text
What was memory-only before
What is now persisted
What intentionally remains runtime-only
Database tables added
Startup reload behavior
Dashboard reload behavior
Endpoints changed
Tests added
Known limitations
```

The verification document must explicitly confirm:

```text
/api/optimization/runs survives restart
Optimization profiles survive restart
Dashboard model weight changes survive restart
Dashboard risk limit changes survive restart
Dynamic model weights reload latest effective profile after restart
Health events or snapshots are visible after restart
Running backtest/walk-forward jobs are not stuck after restart
Runtime-only states are documented as intentionally non-persistent
Startup logs show what was reloaded
```

---

## Acceptance Criteria

This task is complete only if:

1. `/api/optimization/runs` survives API restart.
2. Optimization profiles survive restart.
3. Dashboard model weight changes survive restart.
4. Dashboard risk limit changes survive restart.
5. Dynamic model weights reload latest effective profile after restart.
6. Health events or snapshots are visible after restart.
7. Running backtest/walk-forward jobs are not stuck after restart.
8. Runtime-only states are documented as intentionally non-persistent.
9. Startup logs show what was reloaded.
10. `docs/persistent_state_verification.md` is created.
11. Tests are added for all critical persistence/reload paths.
12. Dashboard clearly shows live, persisted, stale, and unavailable states.

---

## Implementation Rules

1. Do not break the existing working backtest persistence.
2. Do not persist WebSocket subscriber queues.
3. Do not persist dashboard selected tab unless using frontend local storage only.
4. Do not use stale latest price for live execution or live recommendation.
5. Keep memory cache allowed, but database must become the source of truth for persistent state.
6. All important dashboard setting changes must save to database.
7. Add migrations safely.
8. Add startup reload logs.
9. Add clear dashboard empty states.
10. Update documentation after implementation.

---

## Final Recommendation

Do this before adding new prediction features.

The current system is becoming serious, so the next professional step is:

```text
Make every important state durable and restart-safe.
```

After that, safely move to deeper improvements such as:

```text
real optimization
better walk-forward model retraining
live/demo execution comparison
advanced strategy experiments
```
