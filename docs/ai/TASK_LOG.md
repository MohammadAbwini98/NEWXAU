# Task Log

## 2026-07-21 - Initial GitHub Publication

### Agent / Tool

Codex

### Task

Initialize the local NEWXAU project as a Git repository and publish it to the existing public `MohammadAbwini98/NEWXAU` GitHub repository.

### Files Created / Updated

- `.gitignore`
- `.gitmodules`
- `docs/ai/TASK_LOG.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/DECISIONS.md`

### Summary

Prepared the source tree for its initial GitHub publication. Credentials, the local virtual environment, PostgreSQL/runtime state, dataset caches, and downloaded or trained model weights remain local and ignored. The clean third-party `vendor/Kronos` checkout is represented as a Git submodule pointing to `https://github.com/shiyu-coder/Kronos.git` instead of copying its nested Git history into NEWXAU.

### Checks Run

- `gh auth status`
- Common private-key and token signature scan across staged files
- Tracked file size audit and ignore-rule verification
- `.\.venv\Scripts\python.exe -m pytest tests\test_config_defaults.py tests\test_market_sessions.py -q` (`6 passed`, `13 subtests passed`)
- `node scripts/ai-memory/check-memory.mjs`

### Remaining Notes

Model weights and local runtime data are intentionally not versioned. Fresh clones should initialize the Kronos dependency with `git submodule update --init --recursive` and download or train model artifacts through the project scripts.

## 2026-07-15 - Dashboard Market Session Schedule

### Agent / Tool

Codex

### Task

Show all gold market sessions with their open/close times on the main dashboard and clearly highlight the active session.

### Files Created / Updated

- `src/gold_signal_system/dashboard_static/index.html`
- `tests/test_dashboard_startup.py`
- `docs/ai/TASK_LOG.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/KNOWN_ISSUES.md`

### Summary

Added a responsive market-session schedule to the top of the main dashboard using the existing `/api/execution/control` session configuration. Sessions are ordered chronologically and show readable names, Jordan-local start/end times, and Control Unit enabled/disabled or market-closed status. The current session uses a distinct visual treatment plus explicit `Active now` text and `aria-current`, so the state does not depend on color alone. Daily Break remains visibly non-trading, and the UI explains its priority over overlapping schedules.

The implementation preserves the loaded `session_config` after Control Unit toggle saves and adds mobile layouts for adaptive and single-column session cards. No API, market-session classification, Control Unit behavior, or execution setting changed.

### Checks Run

- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py -q` (`10 passed`, `4` existing FastAPI `on_event` deprecation warnings)
- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py tests\test_execution_control.py tests\test_market_sessions.py tests\test_capital_execution.py -q` (`46 passed`, `13 subtests passed`, `4` existing FastAPI `on_event` deprecation warnings)
- Inline dashboard JavaScript parsed successfully with Node `new Function(...)` syntax validation.
- The running dashboard returned HTTP 200 and served the new market-session renderer, active-state label, and Jordan timezone text.
- `node scripts\ai-memory\check-memory.mjs`

### Remaining Notes

Browser-level visual verification is still required because the repository does not currently include a frontend browser-automation suite.

## 2026-07-15 - Capital.com Candle Session Recovery

### Agent / Tool

Codex

### Task

Investigated and fixed why the running Control Unit instance generated no new trades after Capital.com candle polling began returning HTTP 401 while websocket prices remained live.

### Files Created / Updated

- `src/gold_signal_system/providers.py`
- `tests/test_pipeline.py`
- `docs/ai/TASK_LOG.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/DECISIONS.md`

### Summary

The Control Unit was enforcing its persisted session/direction configuration correctly, but the background signal worker had stopped completing cycles because `CapitalComCandleProvider` cached its authenticated state after the broker REST token expired. Added one-time HTTP 401 recovery that clears the cached session headers, authenticates again, and retries the candle request once. Authentication now requires both Capital.com session tokens before the provider marks itself authenticated.

Added mocked regression coverage for successful 401 re-authentication and for rejecting incomplete authentication responses. No execution settings, Control Unit settings, database schema, or demo-only safety guard rails changed.

### Checks Run

- `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -k capitalcom_provider -q`
- `.\.venv\Scripts\python.exe -m pytest tests -q --ignore=tests\test_pipeline.py` (`98 passed`, `13 subtests passed`, `4` existing FastAPI `on_event` deprecation warnings)
- `.\.venv\Scripts\python.exe -m compileall -q src\gold_signal_system\providers.py tests\test_pipeline.py`
- `node scripts\ai-memory\check-memory.mjs`
- `.\.venv\Scripts\python.exe -m pytest tests -q` was stopped after roughly three minutes of sustained high CPU with no completed result, consistent with the documented slow full-pipeline suite behavior.

### Remaining Notes

The running API uses `reload=False` and still needs a controlled restart to load this fix. Because automatic demo execution is armed and the current Control Unit can permit orders during `US_OVERLAP`, the diagnostic/fix session did not restart the service or trigger a live cycle automatically.

## 2026-07-06 - Background Cycle Health Visibility

### Agent / Tool

Codex

### Task

Investigated why `US_OVERLAP` had no trades on 2026-07-06 and why `/api/system/health` reported stale `1h` candles while live ticks were still fresh.

### Files Created / Updated

- `src/gold_signal_system/api.py`
- `tests/test_dashboard_startup.py`
- `docs/ai/TASK_LOG.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/KNOWN_ISSUES.md`

### Summary

The 404 log lines were requests to non-existent diagnostic endpoints, not broker execution failures. Direct Capital.com candle-provider checks returned fresh `1m`, `5m`, `15m`, `1h`, and `4h` candles, and a direct signal-cycle run generated a fresh `US_OVERLAP` signal. The stale health message came from the running API process's in-memory candle store, which had not been refreshed by the background cycle worker since the morning.

Added durable background-cycle worker state in `api.py`: last start/success/error timestamps, last signal time/session, consecutive error count, stale detection based on live-cycle interval, automatic restart if the task terminates unexpectedly, and persisted health events for worker failures. `/api/system/health` now includes a `background_cycle` object and category so stale candles can be distinguished from worker failure/staleness.

### Checks Run

- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py -q`

## 2026-07-03 - Execution Orders Filters And Control Direction Gate

### Agent / Tool

Codex

### Task

Added market-session/date-time filters and filtered statistics to the dashboard Execution > Execution Orders table, plus a Control Unit BUY/SELL direction gate.

### Files Created / Updated

- `src/gold_signal_system/api.py`
- `src/gold_signal_system/contracts.py`
- `src/gold_signal_system/execution_control.py`
- `src/gold_signal_system/storage.py`
- `src/gold_signal_system/dashboard_static/index.html`
- `tests/test_capital_execution.py`
- `tests/test_execution_control.py`
- `docs/ai/TASK_LOG.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/DECISIONS.md`

### Summary

Execution Orders can now be filtered by canonical XAUUSD market sessions such as `US_OVERLAP`, `ASIA_LOW`, `LONDON_ACTIVE`, `NY_ACTIVE`, and `DAILY_BREAK`, and by requested date/time range using `from_time` and `to_time`. The dashboard adds Session, From, and To filters, a visible Session column, and dynamic filtered statistics for total orders, win rate, W/L/P, confirmed/rejected counts, and by-session counts. The API accepts `market_session`, `from_time`, and `to_time` on `/api/execution/orders` and `/api/execution/orders/export`; both responses include a `statistics` object for the filtered result set. Storage resolves the session filter from either the order payload or the linked recommendation JSON so existing executed orders remain filterable without a schema migration.

The Control Unit now has `allowed_directions` for BUY and SELL, checked by default for backward compatibility. Direction checks compose with session checks, so execution is allowed only when both the signal's market session and trade direction are enabled.

### Checks Run

- `.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py tests\test_execution_control.py tests\test_market_sessions.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py tests\test_execution_control.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py tests\test_market_sessions.py -q`
- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\contracts.py src\gold_signal_system\execution_control.py src\gold_signal_system\storage.py src\gold_signal_system\api.py tests\test_capital_execution.py tests\test_execution_control.py`

## 2026-07-02 - Capital.com Live Price Stream Keepalive

### Agent / Tool

Codex

### Task

Investigated why the dashboard websocket kept reconnecting and the live gold price stopped changing.

### Files Created / Updated

- `src/gold_signal_system/capital_stream.py`
- `src/gold_signal_system/config.py`
- `tests/test_capital_stream.py`
- `docs/ai/TASK_LOG.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/DECISIONS.md`

### Summary

Capital.com's WebSocket API requires a `ping` service message to keep the stream alive; the existing stream worker subscribed to market data and then only waited for quotes. After the provider session aged out or account/session activity interrupted streaming, the backend would reconnect but the dashboard could keep showing the last price, making the live price appear frozen.

Added a provider-compliant keepalive ping loop using `destination: "ping"` every `CAPITALCOM_STREAM_PING_SECONDS` seconds, defaulting to 540 seconds. The stream worker now reports `RECONNECTING` with a retry interval whenever the provider closes or interrupts the stream.

### Checks Run

- `.\.venv\Scripts\python.exe -m pytest tests\test_capital_stream.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py -q`
- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\capital_stream.py src\gold_signal_system\config.py tests\test_capital_stream.py`

## 2026-06-30 - Full Review Cleanup: XAUUSD Defaults And Config Hygiene

### Agent / Tool

Codex

### Task

Reviewed the attached full-codebase cleanup prompt, ran baseline validation, scanned for incomplete/stale markers, and fixed the clearest repo-owned stability/configuration issues.

### Files Created / Updated

- `src/gold_signal_system/config.py`
- `src/gold_signal_system/api.py`
- `src/gold_signal_system/__init__.py`
- `src/gold_signal_system/utils.py`
- `src/gold_signal_system/walk_forward.py`
- `src/gold_signal_system/optimization.py`
- `src/gold_signal_system/storage.py`
- `src/gold_signal_system/dashboard_static/index.html`
- `scripts/backfill_candles.py`
- `scripts/run_api.py`
- `scripts/run_cycle.py`
- `scripts/clean_db.py`
- `db/schema.sql`
- `db/004_backtest_persistence.sql`
- `db/005_persistent_runtime_state.sql`
- `README.md`
- `docs/dashboard-fields.md`
- `tests/test_config_defaults.py`
- `tests/test_dashboard_startup.py`
- `tests/test_persistent_runtime_state.py`
- `tests/test_pipeline.py`
- `docs/ai/PROJECT_BRIEF.md`
- `docs/ai/COMMANDS.md`
- `docs/ai/DEVELOPMENT_WORKFLOW.md`
- `docs/ai/RULES.md`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/DATABASE.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/DECISIONS.md`
- `docs/ai/TASK_LOG.md`

### Summary

Changed built-in runtime/dashboard defaults from stale ETHUSD labels to XAUUSD, including config defaults, dashboard text, script labels, optimization/walk-forward/storage fallbacks, and future SQL defaults. Removed the implicit hardcoded external Windows env-file path from runtime config; external Capital.com/Kronos env imports now require explicit `CAPITAL_ENV_FILE`. Fixed the `scripts/backfill_candles.py` docstring escape warning and replaced placeholder AI memory docs with repository-specific content.

SQL changes are non-destructive default/comment updates for future initialization/migrations. Existing database rows are not rewritten by this change.

### Checks Run

- `.\.venv\Scripts\python.exe -m compileall src scripts tests`
- `.\.venv\Scripts\python.exe -m pytest tests\test_config_defaults.py tests\test_market_sessions.py tests\test_execution_control.py tests\test_dashboard_startup.py tests\test_persistent_runtime_state.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py::GoldSignalSystemTests::test_end_to_end_recommendation_shape -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_news_intelligence.py tests\test_improvement_services.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests -q --ignore=tests/test_pipeline.py`
- `.\.venv\Scripts\python.exe -m pytest tests\test_config_defaults.py tests\test_market_sessions.py tests\test_execution_control.py tests\test_dashboard_startup.py tests\test_persistent_runtime_state.py tests\test_pipeline.py -q` timed out after 304 seconds.

### Remaining Notes

Run the full suite with a longer timeout if all `tests/test_pipeline.py` cases must be verified in one command. Browser-check the dashboard labels and Control Unit tab before relying on the UI in demo/live operation.

## 2026-06-30 - Jordan-Time Gold Session Control Unit

### Agent / Tool

Codex

### Task

Reviewed the attached market-session prompt and made Control Unit/session consumers follow XAUUSD sessions in Jordan time (`Asia/Amman`).

### Files Created / Updated

- `src/gold_signal_system/market_sessions.py`
- `src/gold_signal_system/contracts.py`
- `src/gold_signal_system/execution_control.py`
- `src/gold_signal_system/indicator_engine.py`
- `src/gold_signal_system/dynamic_weights.py`
- `src/gold_signal_system/news_intelligence/ai_analyzer.py`
- `src/gold_signal_system/api.py`
- `src/gold_signal_system/dashboard_static/index.html`
- `tests/test_market_sessions.py`
- `tests/test_execution_control.py`
- `tests/test_news_intelligence.py`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/ARCHITECTURE.md`
- `docs/ai/TESTING.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/DECISIONS.md`
- `docs/ai/TASK_LOG.md`

### Summary

Added a canonical gold session resolver using `Asia/Amman` and half-open intervals: `DAILY_BREAK` (`00:00-01:00`), `ASIA_LOW` (`01:00-10:00` effective runtime), `LONDON_ACTIVE` (`10:00-16:00`), `US_OVERLAP` (`16:00-19:00`), and `NY_ACTIVE` (`19:00-00:00`). `DAILY_BREAK` has highest priority, is non-trading, and blocks Control Unit approval even if a payload enables it. Existing old labels normalize to the new session names.

Also made the manual news API test explicitly enable AI analysis so it is not affected by execution-control tests that disable `NEWS_AI_ANALYSIS_ENABLED` in the process environment.

### Checks Run

- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\market_sessions.py src\gold_signal_system\contracts.py src\gold_signal_system\execution_control.py src\gold_signal_system\indicator_engine.py src\gold_signal_system\dynamic_weights.py src\gold_signal_system\news_intelligence\ai_analyzer.py tests\test_market_sessions.py tests\test_execution_control.py`
- `.\.venv\Scripts\python.exe -m pytest tests\test_market_sessions.py tests\test_execution_control.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_improvement_services.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_news_intelligence.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_market_sessions.py tests\test_execution_control.py tests\test_improvement_services.py tests\test_news_intelligence.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_pipeline.py -q` timed out after 244 seconds.
- `node scripts\ai-memory\check-memory.mjs`

### Remaining Notes

Browser-check the Control Unit tab to confirm the new labels and Jordan timestamp render as expected. The full pipeline test should be rerun in an environment where its long runtime is acceptable.

## 2026-06-30 - Forced Capital.com Account Selection Before Orders

### Agent / Tool

Codex

### Task

Hardened Capital.com execution so broker orders cannot rely on a cached selected account when `CAPITAL_EXECUTION_ACCOUNT_NAME` changes or the broker session drifts.

### Files Created / Updated

- `src/gold_signal_system/capital_execution.py`
- `tests/test_capital_execution.py`
- `tests/test_execution_control.py`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/DECISIONS.md`
- `docs/ai/TASK_LOG.md`

### Summary

`CapitalExecutionClient.select_account()` now accepts `force=True` to always send `PUT /session` for the configured account. `CapitalExecutionService` forces account selection before open-position checks and again immediately before `POST /positions`, validates that the selected account matches the configured account name/id, and repeats the forced selection after a 401 re-authentication. Unit tests now isolate `CAPITAL_EXECUTION_ACCOUNT_NAME=NEWXAU` from local `.env` values and include a regression that fails if order submission occurs without a fresh forced account selection.

### Checks Run

- `.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py tests\test_execution_control.py -q`
- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\capital_execution.py tests\test_capital_execution.py tests\test_execution_control.py`
- `node scripts\ai-memory\check-memory.mjs`
- `.\.venv\Scripts\python.exe -m pytest tests -q` timed out after 184 seconds.

### Remaining Notes

Use `/api/execution/status` before execution to verify the running process reports the intended `account_name` and latest account snapshot.

## 2026-06-27 - Capital.com Execution Control Unit

### Agent / Tool

Codex

### Task

Implemented the Control Unit plan for Capital.com execution controls.

### Files Created / Updated

- `src/gold_signal_system/contracts.py`
- `src/gold_signal_system/execution_control.py`
- `src/gold_signal_system/capital_execution.py`
- `src/gold_signal_system/api.py`
- `src/gold_signal_system/storage.py`
- `src/gold_signal_system/dashboard_static/index.html`
- `db/010_execution_control.sql`
- `scripts/init_db.py`
- `tests/test_execution_control.py`
- `tests/test_dashboard_startup.py`
- `docs/ai/CURRENT_STATE.md`
- `docs/ai/FEATURES.md`
- `docs/ai/ARCHITECTURE.md`
- `docs/ai/TESTING.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/TASK_LOG.md`

### Summary

Added a Control Unit dashboard tab and API. Operators can allow/block Capital.com execution by market session and optionally allow only trades where the ensemble is opposite to Kronos or directional model votes are tied. The execution gate runs inside `CapitalExecutionService` before broker submission, persists config in `system_settings`, audits decisions in `execution_control_decisions`, and exposes decision/execution/what-if statistics. Automatic execution blocks are audit-only and do not create noisy `execution_orders` rows; manual execution attempts still produce visible BLOCKED rows.

### Checks Run

- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\contracts.py src\gold_signal_system\execution_control.py src\gold_signal_system\capital_execution.py src\gold_signal_system\api.py src\gold_signal_system\storage.py`
- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system tests\test_execution_control.py tests\test_dashboard_startup.py tests\test_capital_execution.py`
- `.\.venv\Scripts\python.exe -m pytest tests\test_execution_control.py -q`
- `.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py tests\test_execution_control.py -q`
- `$env:CAPITAL_EXECUTION_ACCOUNT_NAME='NEWXAU'; .\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py -q`
- `node scripts/ai-memory/check-memory.mjs`

### Remaining Notes

Apply `db/010_execution_control.sql` through `python scripts/init_db.py` in PostgreSQL-backed deployments before expecting persistent Control Unit decision history.

## 2026-06-27 - Execution Orders Bulk Full-Payload Export

### Agent / Tool

Codex

### Task

Updated the Execution Orders table export so the downloaded JSON contains the full dashboard payload for each signal-trade record.

### Files Created / Updated

- `src/gold_signal_system/api.py`
- `tests/test_capital_execution.py`
- `docs/ai/FEATURES.md`
- `docs/ai/TESTING.md`
- `docs/ai/KNOWN_ISSUES.md`
- `docs/ai/TASK_LOG.md`

### Summary

`/api/execution/orders/export` now exports each item as `{ execution_order, signal_detail, broker_response, broker_confirm }`, matching the per-row dashboard Full Payload modal structure. Added a regression test for the export shape.

### Checks Run

- `.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\api.py`
- `.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py::CapitalExecutionApiTests::test_execution_orders_export_uses_full_dashboard_payload_shape -q`
- `$env:CAPITAL_EXECUTION_ACCOUNT_NAME='NEWXAU'; .\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py -q`
- `node scripts/ai-memory/check-memory.mjs`

### Remaining Notes

Superseded on 2026-06-30: `tests/test_capital_execution.py` now sets `CAPITAL_EXECUTION_ACCOUNT_NAME=NEWXAU` internally for fake-client isolation.

## 2026-06-27 - AI Memory Setup Tailored For NEWXAU

### Agent / Tool

Codex

### Task

Reviewed the existing `setup-ai-memory.mjs` bootstrap script and adapted it for the NEWXAU/KRONOS trading repository.

### Files Created / Updated

- `C:\Users\moham\Downloads\setup-ai-memory\setup-ai-memory.mjs`
- `C:\Users\moham\Downloads\setup-ai-memory\setup-ai-memory-user-manual.md`
- `AGENTS.md`
- `scripts/ai-memory/check-memory.mjs`
- `docs/ai/TASK_LOG.md`

### Summary

The setup script now auto-detects NEWXAU, writes project-specific memory docs, protects `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` from accidental overwrite, supports `--force-agent-files` for intentional replacement, and installs a cleaner memory checker with less noisy secret detection.

### Checks Run

- `node --check C:\Users\moham\Downloads\setup-ai-memory\setup-ai-memory.mjs`
- `node scripts/ai-memory/check-memory.mjs`

### Remaining Notes

Use `--force` only to repair generated memory docs/skills. Use `--force --force-agent-files` only when intentionally replacing the protected agent instruction files.
