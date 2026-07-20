# Project Brief

Last updated: 2026-06-30

## Confirmed

NEWXAU is a Python/FastAPI XAUUSD signal recommendation system with automated signal generation, backtesting, paper trading, dashboard APIs, optional news intelligence, and guarded Capital.com execution.

## Main Goal

Generate, validate, display, and optionally execute XAUUSD trading recommendations while preserving risk controls, session controls, demo/live safety guard rails, and PostgreSQL/in-memory resilience.

## Main Users

- Operators using the dashboard to monitor signals, execution, risk, models, and health.
- Developers/agents maintaining pipeline, execution, storage, tests, and documentation.
- Strategy researchers using backtesting, walk-forward testing, threshold optimization, and model-performance tooling.

## Main Workflows

- Run API/dashboard with `python scripts/run_api.py`.
- Run one signal cycle with `python scripts/run_cycle.py`.
- Generate recommendations through the Data -> Indicators -> Models -> Strategy -> Trade Plan -> Risk -> Control Unit pipeline.
- Review or execute eligible signals through dashboard/API endpoints.
- Run backtests and walk-forward reports from scripts or dashboard APIs.
- Collect/analyze XAUUSD-relevant news when news intelligence is enabled.

## High-Level Modules

- Backend/API: `src/gold_signal_system/api.py`
- Pipeline orchestration: `src/gold_signal_system/pipeline.py`
- Storage: `src/gold_signal_system/storage.py`
- Capital.com execution/streaming: `capital_execution.py`, `capital_stream.py`, `providers.py`
- Session control: `market_sessions.py`, `execution_control.py`
- Dashboard: `src/gold_signal_system/dashboard_static/`
- Tests: `tests/`
- Database schema/migrations: `db/`

## What This Project Is Not

- It is not safe for autonomous live execution unless the explicit Capital.com execution flags, account settings, market conditions, and demo/live safeguards are verified.
- It is not a frontend-framework app; the dashboard is vanilla HTML/JS.
- It is not allowed to store real secrets in documentation or committed config.

## External Dependencies

Capital.com credentials, PostgreSQL, external news/AI providers, and model artifacts can all be absent. Runtime code should degrade gracefully to safe fallbacks where the architecture already supports that.
