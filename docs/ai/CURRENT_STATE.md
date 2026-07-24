# Current State

Last updated: 2026-07-24

## What Works

- **AI-agent architecture:** `AGENTS.md` and `docs/ai/` are the shared source of truth. `docs/ai/README.md` defines token-efficient reading order, while `docs/ai/HANDOFF.md` stores active transfer state. Tool-neutral procedures live under `.agents/`; Claude uses thin `.claude/` adapters, Gemini uses `.gemini/commands`, and Cursor uses path-scoped `.cursor/rules`. The memory checker validates required memory/handoff files, scans adapter text for secret-like values, and warns about optional adapter gaps.
- The project is version-controlled in the public `MohammadAbwini98/NEWXAU` GitHub repository; `vendor/Kronos` is tracked as an upstream Git submodule.
- FastAPI API/dashboard entry point exists via `scripts/run_api.py`.
- A headless loopback entry exists via `scripts/run_backend.py`; it supports a
  dynamic port, machine-readable readiness, desktop token authentication, and
  desktop-managed graceful shutdown.
- The legacy dashboard remains in `src/gold_signal_system/dashboard_static/`.
- The AWKIT-inspired Electron/React/TypeScript application lives under `app/`.
  It owns the Python child process, uses a narrow preload bridge, stores desktop
  settings under `%LOCALAPPDATA%\NEWXAU`, encrypts configured secrets with
  Electron `safeStorage`, and connects to the preserved REST/WebSocket contract.
- Packaged desktop startup fails closed when the bundled Python runtime is
  absent. Backend logs and desktop diagnostics pass through centralized
  sensitive-data redaction.
- Clean desktop installs without a configured data provider or complete
  Capital.com credentials start with the synthetic provider instead of
  crashing during backend import. An explicit `DATA_PROVIDER`,
  `CAPITAL_ENV_FILE`, or complete encrypted Capital.com credential set remains
  authoritative.
- Desktop routes now cover Overview, Live Signal, Execution, Control Unit,
  Signal History, Models, Indicators, Risk, Backtesting, Optimization, Replay,
  News Intelligence, System Health, and Settings.
- Storage supports PostgreSQL and in-memory fallback.
- PostgreSQL startup attempts are bounded for both primary storage and News
  Intelligence. An unavailable configured database falls back to in-memory
  instead of indefinitely blocking desktop readiness.
- Capital.com execution integration exists and keeps demo/safety guard rails.
- Capital.com execution forces broker account selection for `CAPITAL_EXECUTION_ACCOUNT_NAME` immediately before market order submission and validates the selected account.
- Execution Orders can be listed, inspected, filtered by market session and requested date/time range, summarized with dynamic filtered statistics, and exported with full dashboard payload JSON.
- Control Unit can persist execution gates, block Capital.com execution before broker submission by market session and BUY/SELL direction, audit decisions, and show statistics. Dashboard checkbox changes are applied optimistically, saved in order, and protected from stale background/WebSocket refresh responses. Auto blocks are audit-only; manual blocks remain visible in Execution Orders.
- Control Unit and signal context use the canonical Jordan-time XAUUSD sessions: `DAILY_BREAK`, `ASIA_LOW`, `LONDON_ACTIVE`, `US_OVERLAP`, and `NY_ACTIVE`. `DAILY_BREAK` is always non-trading.
- The main dashboard shows the canonical market-session schedule with Jordan open/close times, the active session, and each session's current Control Unit enabled/disabled state.
- News Intelligence modules and migrations exist as an optional XAUUSD context/risk layer.
- Runtime and dashboard defaults use the internal instrument `XAUUSD`; the
  default Capital.com market epic is `GOLD`. Explicit broker-symbol
  environment overrides remain authoritative. External Capital/Kronos env
  imports require explicit `CAPITAL_ENV_FILE`; no hardcoded machine-local env
  file is loaded implicitly.
- Capital.com live price streaming sends provider `ping` keepalives every `CAPITALCOM_STREAM_PING_SECONDS` seconds, defaulting to 540 seconds, and reports `RECONNECTING` when the provider stream closes or is interrupted.
- Electron refreshes prices on the backend's `price.tick` event. With a
  non-live provider it labels the latest signal price as a reference rather
  than presenting it as a live quote.
- Capital.com candle polling invalidates expired REST session tokens on HTTP 401, authenticates again, and retries the candle request once so long-running background signal cycles can recover without an API restart.
- `/api/system/health` reports background cycle worker state, including last start/success/error timestamps, last generated signal time/session, consecutive worker errors, and stale-worker detection.
- Every signal cycle reports scored candle quality, freshness, integrity counts, spread/provider/aggregation status, blocking reasons, and stage latency. These fields are exposed by the cycle API and persisted inside signal snapshot risk-filter JSON.
- An opt-in `ENABLE_DATA_QUALITY_GATE` can fail closed before model inference and emit deterministic HOLD abstentions. It is disabled by default pending shadow and out-of-sample validation.
- The legacy backtest engine applies configured spread, round-trip slippage, and commission to net realized R and reports gross/net R plus cost assumptions.

## Partially Implemented / Needs Care

- Downloaded/trained model weights, dataset caches, local PostgreSQL/runtime state, `.env`, and `.venv` are intentionally excluded from Git; fresh clones must initialize the Kronos submodule and provision local artifacts separately.
- Full-suite tests may be slow; Capital.com unit tests isolate account-name env values from local `.env`.
- News collection/analyzer behavior depends on optional configuration and external services.
- Control Unit audit statistics require `db/010_execution_control.sql` to be applied for PostgreSQL persistence; in-memory fallback still works.
- Legacy stored session labels such as `ASIAN`, `LONDON`, `NEW_YORK`, `LONDON_NEW_YORK_OVERLAP`, and `ROLLOVER` are accepted as aliases and normalized to the new session names.
- Candle storage used by live signal generation is still in-process memory. Broker failures other than one recoverable 401, or a stalled background worker, can still leave live ticks fresh while signal candles and recommendations stop advancing; check `/api/system/health.background_cycle`.
- Existing walk-forward JSON reports predate the cost-aware legacy simulator and use mock models; they are baselines only and must not be presented as production profitability evidence.
- A local private Python 3.12.10 x64 runtime has passed stable hashed inventory,
  package/DLL, native inference, PostgreSQL driver, relocated backend import,
  and safety-environment verification. Controlled import bytecode is hashed and
  runtime bytecode writes are disabled. The generated runtime is excluded from
  Git.
- Unsigned unpacked, NSIS, and portable packaging has been exercised locally.
  Development and unpacked-package renderer/backend lifecycle smokes reached
  ready and shut down with empty stderr. Signing and clean non-admin machine
  validation remain gated.
- Node 22.12 or newer is required for packaging. The current local Node 18
  runtime can type-check, test, build, and run Electron smoke validation, but
  does not meet the declared packaging toolchain floor and currently fails
  Electron Builder while loading its ESM hashing dependency.
- The legacy dashboard-startup test can enter real local Kronos inference and
  trigger a Windows native `torch`/`safetensors` access violation. Use the safe
  desktop/execution/control/session gate until the native artifact is repaired.

## Must Not Break

- Data -> Indicators -> Models -> Strategy -> Trade Plan -> Risk -> Control Unit -> Execution separation.
- In-memory fallback when PostgreSQL is unavailable.
- Capital.com execution safety controls, especially `CAPITAL_EXECUTION_DEMO_ONLY=1`.
- Legacy dashboard compatibility with vanilla HTML/JS until explicit cutover
  acceptance.
- Desktop REST/WebSocket token enforcement and main-process sender/navigation
  guards.

## Next Logical Steps

- Run `python scripts/init_db.py` in PostgreSQL-backed environments to apply the Control Unit audit table.
- Set `CAPITAL_ENV_FILE` explicitly if an external Capital.com/Kronos-compatible env file should be imported.
- Verify Control Unit toggles in the browser before relying on them during live/demo execution.
- Watch the dashboard `Stream:` pill and `/api/price/latest` after long-running sessions; it should show fresh ticks or an explicit reconnecting status instead of silently freezing.
- Watch `/api/system/health` after long-running sessions; `background_cycle.healthy` should stay true and `background_cycle.last_success_at` should update near the configured live-cycle interval.
- Keep memory docs current after implementation work.
- Reproduce the private Windows runtime/package hashes in the release
  environment, then run clean-machine installer smoke validation.
- Review `docs/desktop/PARITY_MATRIX.md` and explicitly accept the desktop
  surfaces before removing or redirecting the legacy dashboard.
- Run the data-quality gate in shadow/monitor-only mode first, then explicitly enable it only after reviewing block rates and false blocks on versioned out-of-sample data.
- Rerun time-ordered walk-forward and paper/demo validation with identical spread, slippage, and commission assumptions before promoting any strategy or model change.
