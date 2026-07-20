# Backtest / Walk-Forward Dashboard Data Persistence and Execution Fix

## Context

Codex reported the following current behavior:

- No backtest or walk-forward run has been executed in the current dashboard process.
- The dashboard currently reads:

```http
GET /api/backtest/summary
```

- The endpoint currently returns:

```json
{
  "status": "NO_BACKTEST_RUN"
}
```

- Also:

```http
GET /api/backtests
```

returns:

```json
{
  "items": []
}
```

- There is no report folder yet:

```text
reports/walk_forward/
```

- Live signals are now persisted in PostgreSQL.
- Backtest and walk-forward run lists are still mostly process-local/in-memory plus report-file based.
- After restarting `run_api.py`, old backtest run objects are not automatically loaded into the dashboard unless reports exist and are loaded.

## Current Root Cause

The signal system is running and persisting live signals, but no backtest job has been run or loaded. Therefore, the dashboard correctly shows no backtest data.

The deeper architecture issue is that the live signal system and the backtest system are currently separated:

```text
Live Signal System
→ persists signals in PostgreSQL
→ dashboard can show live/persisted signals

Backtest / Walk-Forward System
→ mostly in-memory + report-file based
→ no job executed yet
→ no reports/walk_forward folder
→ dashboard has nothing to load
```

## Main Goal

Make backtest and walk-forward runs:

1. Executable from API and dashboard.
2. Persisted in PostgreSQL.
3. Reloadable after API restart.
4. Saved to report folders.
5. Visible in the dashboard.
6. Connected to the current production Strategy Brain.
7. Not dependent on process-local memory.

---

# Codex Implementation Prompt

## Fix Backtest / Walk-Forward Dashboard Data Persistence and Execution

Codex, review the current backtest and walk-forward implementation.

Current issue:

- Dashboard calls `GET /api/backtest/summary`.
- The endpoint returns `{ "status": "NO_BACKTEST_RUN" }`.
- `GET /api/backtests` returns `{ "items": [] }`.
- There is no `reports/walk_forward/` folder yet.
- Live signals are persisted in PostgreSQL, but backtest/walk-forward runs are mostly process-local/in-memory plus report-file based.
- After restarting `run_api.py`, old backtest objects are not loaded unless report files exist and are manually loaded.

Goal:

Make backtest and walk-forward runs executable, persisted, reloadable after restart, and visible in the dashboard.

---

# Task 1 — Add Backtest Run Persistence

Create PostgreSQL tables/entities for backtest and walk-forward runs.

Required tables:

```text
backtest_runs
backtest_trades
backtest_metrics
walk_forward_runs
walk_forward_folds
walk_forward_reports
```

## `backtest_runs`

Should include:

```text
id
run_id
run_type: BACKTEST / WALK_FORWARD
instrument
timeframe
status: CREATED / RUNNING / COMPLETED / FAILED / CANCELLED
started_at
completed_at
config_json
summary_json
report_path
error_message
created_at
updated_at
```

## `backtest_trades`

Should include:

```text
id
run_id
signal_time
signal_direction
entry_price
stop_loss
take_profit_1
take_profit_2
take_profit_3
exit_price
outcome
pnl
risk_reward
confidence
score
entry_time
exit_time
reason_json
created_at
```

## `walk_forward_folds`

Should include:

```text
id
run_id
fold_number
train_start
train_end
test_start
test_end
status
metrics_json
report_path
created_at
```

Add database migrations safely.

---

# Task 2 — Add API Endpoint to Start Backtest

Add endpoint:

```http
POST /api/backtests/run
```

## Request Example

```json
{
  "run_type": "WALK_FORWARD",
  "instrument": "XAUUSD",
  "timeframe": "5m",
  "start_date": "2025-01-01",
  "end_date": "2026-01-01",
  "initial_balance": 10000,
  "risk_percent": 1.0,
  "strategy_version": "current",
  "threshold_profile": "active",
  "model_weight_profile": "active"
}
```

## Expected Behavior

1. Create run record in PostgreSQL with `RUNNING` status.
2. Execute backtest or walk-forward.
3. Save trades, folds, metrics, and summary to PostgreSQL.
4. Also save report files under:

```text
reports/walk_forward/{run_id}/
```

or:

```text
reports/backtests/{run_id}/
```

5. Mark run as `COMPLETED` or `FAILED`.
6. Return the `run_id`.

## Response Example

```json
{
  "run_id": "WF-20260609-001",
  "status": "RUNNING",
  "message": "Walk-forward backtest started."
}
```

If the process is synchronous for now, return the completed result.

If async is supported, return `RUNNING` and allow polling.

---

# Task 3 — Add Backtest Run List Endpoint

Fix or improve:

```http
GET /api/backtests
```

It must load from PostgreSQL, not only memory.

## Response Example

```json
{
  "items": [
    {
      "run_id": "WF-20260609-001",
      "run_type": "WALK_FORWARD",
      "instrument": "XAUUSD",
      "timeframe": "5m",
      "status": "COMPLETED",
      "started_at": "2026-06-09T10:00:00",
      "completed_at": "2026-06-09T10:12:00",
      "profit_factor": 1.42,
      "win_rate": 0.58,
      "max_drawdown": 0.07,
      "number_of_trades": 124,
      "report_path": "reports/walk_forward/WF-20260609-001/summary.json"
    }
  ]
}
```

---

# Task 4 — Add Latest Backtest Summary Endpoint

Fix:

```http
GET /api/backtest/summary
```

It should:

1. Find the latest completed backtest/walk-forward run from PostgreSQL.
2. Return its summary.
3. If no run exists, return a useful empty state.

## Empty State Example

```json
{
  "status": "NO_BACKTEST_RUN",
  "message": "No backtest has been executed yet.",
  "next_action": "Run a backtest from the dashboard or call POST /api/backtests/run."
}
```

## Completed State Example

```json
{
  "status": "COMPLETED",
  "run_id": "WF-20260609-001",
  "run_type": "WALK_FORWARD",
  "instrument": "XAUUSD",
  "timeframe": "5m",
  "win_rate": 0.58,
  "profit_factor": 1.42,
  "max_drawdown": 0.07,
  "number_of_trades": 124,
  "average_rr": 1.86,
  "buy_precision": 0.61,
  "sell_precision": 0.55,
  "report_path": "reports/walk_forward/WF-20260609-001/summary.json"
}
```

---

# Task 5 — Load Existing Reports After Restart

On API startup:

1. Check PostgreSQL for existing backtest runs.
2. Check report folders:

```text
reports/backtests/
reports/walk_forward/
```

3. If report folders exist but DB records are missing, import report metadata into PostgreSQL.
4. Do not duplicate existing runs.
5. Log how many runs were loaded.

## Required Log Example

```text
Loaded 4 backtest runs from PostgreSQL.
Imported 2 walk-forward reports from reports/walk_forward/.
```

---

# Task 6 — Dashboard Backtest Run Button

Add dashboard button:

```text
Run Walk-Forward Backtest
```

The button should:

1. Open a small config modal.
2. Let user select:
   - instrument
   - timeframe
   - start date
   - end date
   - run type: `BACKTEST` / `WALK_FORWARD`
   - risk percent
   - initial balance
3. Call:

```http
POST /api/backtests/run
```

4. Show status:
   - Running
   - Completed
   - Failed
5. Refresh:
   - `/api/backtests`
   - `/api/backtest/summary`

---

# Task 7 — Dashboard Backtest Data Panels

Dashboard should show:

```text
Latest Backtest Summary
Walk-Forward Summary
Backtest Run History
Trades Table
Fold Results
Metrics Cards
Report Download/Open Link
```

## Cards

```text
Win Rate
Profit Factor
Max Drawdown
Number of Trades
Average R:R
BUY Precision
SELL Precision
Blocked Signals
```

If no run exists, show:

```text
No backtest has been run yet.
Click "Run Walk-Forward Backtest" to generate results.
```

Do not show confusing `N/A` values.

---

# Task 8 — Save Report Files

Each walk-forward run must create:

```text
reports/walk_forward/{run_id}/summary.json
reports/walk_forward/{run_id}/folds.csv
reports/walk_forward/{run_id}/trades.csv
reports/walk_forward/{run_id}/metrics.json
reports/walk_forward/{run_id}/recommendations.md
```

Each normal backtest run must create:

```text
reports/backtests/{run_id}/summary.json
reports/backtests/{run_id}/trades.csv
reports/backtests/{run_id}/metrics.json
reports/backtests/{run_id}/recommendations.md
```

The dashboard should link to these files if available.

---

# Task 9 — Connect Backtest to Current Strategy Brain

Backtest must use the same production Strategy Brain used by live recommendations.

Do not create a separate fake strategy.

Backtest pipeline should call:

```text
Historical Candles
→ Indicator Engine
→ Model Prediction Provider / Stored Prediction Provider
→ Strategy Brain
→ Entry/SL/TP Engine
→ Risk Engine
→ Trade Simulator
→ Metrics Calculator
→ Persistence + Reports
```

If real model inference is unavailable during backtest, support a clear mode:

```text
model_mode = STORED_PREDICTIONS / LIVE_INFERENCE / MOCK_FOR_TEST_ONLY
```

Dashboard and report must clearly show which mode was used.

---

# Task 10 — Add Tests

Add tests for:

```text
POST /api/backtests/run creates DB record
GET /api/backtests loads records after restart
GET /api/backtest/summary returns latest completed run
reports are written to correct folder
walk-forward folds are persisted
backtest trades are persisted
NO_BACKTEST_RUN state works correctly
dashboard button calls correct API
```

---

# Task 11 — Final Verification Report

Create:

```text
docs/backtest_dashboard_fix_verification.md
```

Include:

```text
What was broken
What was fixed
Which endpoints were added/updated
Which database tables were added
Where reports are saved
How to run a backtest from API
How to run a backtest from dashboard
How data is loaded after restart
Known limitations
Next improvements
```

---

# Acceptance Criteria

The task is complete only if:

1. `POST /api/backtests/run` can start a run.
2. `GET /api/backtests` returns persisted runs from PostgreSQL.
3. `GET /api/backtest/summary` returns latest completed run.
4. Report files are created under `reports/walk_forward/{run_id}` or `reports/backtests/{run_id}`.
5. Dashboard has a button to run walk-forward backtest.
6. Dashboard shows a clean empty state before first run.
7. Dashboard shows real metrics after a run.
8. Data survives API restart.
9. No backtest data depends only on process-local memory.
10. Verification document is created.

---

# Final Expected Behavior

Before any run:

```json
{
  "status": "NO_BACKTEST_RUN",
  "message": "No backtest has been executed yet.",
  "next_action": "Run a backtest from the dashboard or call POST /api/backtests/run."
}
```

After running a walk-forward backtest:

```json
{
  "status": "COMPLETED",
  "run_id": "WF-20260609-001",
  "run_type": "WALK_FORWARD",
  "instrument": "XAUUSD",
  "timeframe": "5m",
  "win_rate": 0.58,
  "profit_factor": 1.42,
  "max_drawdown": 0.07,
  "number_of_trades": 124,
  "average_rr": 1.86,
  "buy_precision": 0.61,
  "sell_precision": 0.55,
  "report_path": "reports/walk_forward/WF-20260609-001/summary.json"
}
```

After restarting `run_api.py`:

```text
Dashboard still shows previous backtest/walk-forward runs because data is loaded from PostgreSQL and/or report files.
```

---

# Important Notes

- Do not rely on process-local memory for completed backtest history.
- Do not show confusing `N/A` values on the dashboard.
- Backtest must use the current Strategy Brain, not a separate fake strategy.
- If mock model predictions are used, label the run clearly as `MOCK_FOR_TEST_ONLY`.
- If real model inference is not available, support `STORED_PREDICTIONS` mode.
- The dashboard must show whether the run used `STORED_PREDICTIONS`, `LIVE_INFERENCE`, or `MOCK_FOR_TEST_ONLY`.
