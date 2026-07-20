# Current State

Last updated: 2026-07-21

## What Works

- The project is version-controlled in the public `MohammadAbwini98/NEWXAU` GitHub repository; `vendor/Kronos` is tracked as an upstream Git submodule.
- FastAPI API/dashboard entry point exists via `scripts/run_api.py`.
- The dashboard uses vanilla HTML/JS in `src/gold_signal_system/dashboard_static/`.
- Storage supports PostgreSQL and in-memory fallback.
- Capital.com execution integration exists and keeps demo/safety guard rails.
- Capital.com execution forces broker account selection for `CAPITAL_EXECUTION_ACCOUNT_NAME` immediately before market order submission and validates the selected account.
- Execution Orders can be listed, inspected, filtered by market session and requested date/time range, summarized with dynamic filtered statistics, and exported with full dashboard payload JSON.
- Control Unit can persist execution gates, block Capital.com execution before broker submission by market session and BUY/SELL direction, audit decisions, and show statistics. Auto blocks are audit-only; manual blocks remain visible in Execution Orders.
- Control Unit and signal context use the canonical Jordan-time XAUUSD sessions: `DAILY_BREAK`, `ASIA_LOW`, `LONDON_ACTIVE`, `US_OVERLAP`, and `NY_ACTIVE`. `DAILY_BREAK` is always non-trading.
- The main dashboard shows the canonical market-session schedule with Jordan open/close times, the active session, and each session's current Control Unit enabled/disabled state.
- News Intelligence modules and migrations exist as an optional XAUUSD context/risk layer.
- Runtime and dashboard defaults now use XAUUSD. External Capital/Kronos env imports require explicit `CAPITAL_ENV_FILE`; no hardcoded machine-local env file is loaded implicitly.
- Capital.com live price streaming sends provider `ping` keepalives every `CAPITALCOM_STREAM_PING_SECONDS` seconds, defaulting to 540 seconds, and reports `RECONNECTING` when the provider stream closes or is interrupted.
- Capital.com candle polling invalidates expired REST session tokens on HTTP 401, authenticates again, and retries the candle request once so long-running background signal cycles can recover without an API restart.
- `/api/system/health` reports background cycle worker state, including last start/success/error timestamps, last generated signal time/session, consecutive worker errors, and stale-worker detection.

## Partially Implemented / Needs Care

- Downloaded/trained model weights, dataset caches, local PostgreSQL/runtime state, `.env`, and `.venv` are intentionally excluded from Git; fresh clones must initialize the Kronos submodule and provision local artifacts separately.
- Full-suite tests may be slow; Capital.com unit tests isolate account-name env values from local `.env`.
- News collection/analyzer behavior depends on optional configuration and external services.
- Control Unit audit statistics require `db/010_execution_control.sql` to be applied for PostgreSQL persistence; in-memory fallback still works.
- Legacy stored session labels such as `ASIAN`, `LONDON`, `NEW_YORK`, `LONDON_NEW_YORK_OVERLAP`, and `ROLLOVER` are accepted as aliases and normalized to the new session names.
- Candle storage used by live signal generation is still in-process memory. Broker failures other than one recoverable 401, or a stalled background worker, can still leave live ticks fresh while signal candles and recommendations stop advancing; check `/api/system/health.background_cycle`.

## Must Not Break

- Data -> Indicators -> Models -> Strategy -> Trade Plan -> Risk -> Control Unit -> Execution separation.
- In-memory fallback when PostgreSQL is unavailable.
- Capital.com execution safety controls, especially `CAPITAL_EXECUTION_DEMO_ONLY=1`.
- Dashboard compatibility with vanilla HTML/JS.

## Next Logical Steps

- Run `python scripts/init_db.py` in PostgreSQL-backed environments to apply the Control Unit audit table.
- Set `CAPITAL_ENV_FILE` explicitly if an external Capital.com/Kronos-compatible env file should be imported.
- Verify Control Unit toggles in the browser before relying on them during live/demo execution.
- Watch the dashboard `Stream:` pill and `/api/price/latest` after long-running sessions; it should show fresh ticks or an explicit reconnecting status instead of silently freezing.
- Watch `/api/system/health` after long-running sessions; `background_cycle.healthy` should stay true and `background_cycle.last_success_at` should update near the configured live-cycle interval.
- Keep memory docs current after implementation work.
