# Features

Last updated: 2026-07-21

## Existing Features

- Market data ingestion and indicator processing.
- XAUUSD-first runtime/dashboard defaults with explicit environment override support.
- Model ensemble signal generation.
- Strategy brain and trade-plan generation.
- Risk checks before execution.
- Capital.com execution integration with demo/live safety guard rails.
- Recoverable Capital.com candle polling that re-authenticates and retries once after an expired REST session returns HTTP 401.
- Forced Capital.com account selection before market order submission using `CAPITAL_EXECUTION_ACCOUNT_NAME`.
- Control Unit dashboard/API for Capital.com execution gates by market session, BUY/SELL direction, and Kronos-vs-ensemble relation.
- Responsive main-dashboard market-session schedule with Jordan open/close times, active-session highlighting, and Control Unit availability labels.
- Central XAUUSD market-session classification in Jordan time (`Asia/Amman`) for indicators, Control Unit, model context, and rules-based news labels.
- FastAPI API and vanilla HTML/JS dashboard.
- Execution Orders dashboard view with status/outcome/direction/session/date-time filters, dynamic filtered statistics, per-row detail modal, and bulk full-payload JSON export.
- Backtesting and paper-trading scripts.
- PostgreSQL persistence with in-memory fallback.
- Optional News Intelligence modules for XAUUSD context and dashboard visibility.
- Candle-quality scoring for freshness, gaps, duplicates, invalid rows, outliers, ordering, spread, provider state, and aggregation completeness.
- Default-off fail-closed data-quality gate that skips model adapters and produces auditable deterministic HOLD abstentions.
- Per-cycle stage timing in API responses and persisted signal snapshot context.
- Cost-aware legacy backtest results with gross/net R, blocked-signal counts, and explicit cost assumptions.

## Execution Orders Payload Export

The Execution Orders table and export endpoint support filtering by broker/order status, outcome, direction, signal id, requested date/time range (`from_time`/`to_time` on `requested_at`), and canonical market session (`DAILY_BREAK`, `ASIA_LOW`, `LONDON_ACTIVE`, `US_OVERLAP`, `NY_ACTIVE`). The filtered response includes dynamic statistics (`total`, status/outcome/direction/session counts, W/L/P, confirmed/rejected counts, and win rate) before pagination. The export endpoint returns one JSON file containing every filtered signal-trade record. Each item uses the same structure shown in the dashboard detail modal:

- `execution_order`
- `signal_detail`
- `broker_response`
- `broker_confirm`

## Control Unit

The Control Unit is a dashboard tab and API-backed execution gate. It can:

- Enable/disable Capital.com execution by market session: `DAILY_BREAK`, `ASIA_LOW`, `LONDON_ACTIVE`, `US_OVERLAP`, and `NY_ACTIVE`.
- Enable/disable Capital.com execution by BUY/SELL trade direction; direction and session gates compose with AND semantics.
- Resolve current/session tags using `Asia/Amman` half-open intervals. `DAILY_BREAK` (`00:00-01:00`) overrides `ASIA_LOW` and is always treated as non-trading.
- Optionally allow execution only when the ensemble is opposite to Kronos or directional model votes are tied.
- Persist configuration in `system_settings` under `execution_control.active`.
- Audit gate decisions in `execution_control_decisions`.
- Show decision, execution outcome, relation, what-if statistics, and the Jordan local timestamp used for current-session classification.

## Dashboard Market Sessions

The main dashboard renders the API-provided canonical gold session schedule in chronological order. Each session shows its Jordan-local open/close time and whether the Control Unit currently enables it. The active session is identified with both a highlighted treatment and explicit `Active now` text, including `aria-current` for assistive technology. The layout collapses from five columns to an adaptive grid and then one column on narrow screens.

## Capital.com Account Safety

Before submitting a broker market order, execution forces Capital.com session selection to the configured `CAPITAL_EXECUTION_ACCOUNT_NAME` and validates the selected account name/id. This avoids relying on cached account state when a process has been running for a long time or the broker session has drifted.

## Capital.com Candle Session Recovery

The candle provider requires both `CST` and `X-SECURITY-TOKEN` before marking authentication successful. If a candle request receives HTTP 401, it removes only those session headers, authenticates again, and retries the request once. A second failure is returned normally to the background-cycle health and retry layers.

## Feature Ownership By Module

- API/dashboard endpoints: `src/gold_signal_system/api.py`
- Dashboard UI: `src/gold_signal_system/dashboard_static/index.html`
- Persistence: `src/gold_signal_system/storage.py`
- Execution: `src/gold_signal_system/capital_execution.py`
- Control Unit: `src/gold_signal_system/execution_control.py`
- Gold session schedule: `src/gold_signal_system/market_sessions.py`
- Risk: `src/gold_signal_system/risk_engine.py`
- News Intelligence: `src/gold_signal_system/news_intelligence/`
- Data validation and aggregation: `src/gold_signal_system/data_engine.py`
- Pipeline quality gate and timing: `src/gold_signal_system/pipeline.py`
- Legacy cost-aware simulation: `src/gold_signal_system/backtesting.py`
