# Decisions

Last updated: 2026-07-24

## 2026-07-24 - Retain Legacy Dashboard Until Explicit Parity Acceptance

**Decision:** Keep the legacy dashboard available for every desktop capability
classified `Legacy fallback`. Treat the absence of direct Electron order
submission as `Restricted by design`.

**Reason:** Paper Trading, diagnostics, replay workflow depth, detailed
charts/filters, desktop-native exports, and some settings are not yet accepted
as complete desktop parity. Direct renderer execution would weaken the intended
process boundary.

**Impact:** PR #2 remains a draft. Legacy removal requires a complete parity
matrix and explicit product cutover approval.

**Related files:** `docs/desktop/PARITY_MATRIX.md`,
`app/main/backendProcessManager.ts`

## 2026-07-24 - Packaged Python Is Private And Fail-Closed

**Decision:** Packaged mode may launch only
`resources/python/python.exe`. Development may use the staged private runtime,
then `.venv`, and may use system Python only with
`NEWXAU_ALLOW_SYSTEM_PYTHON=1`.

**Reason:** A packaged trading application must not silently inherit an
unverified machine-wide interpreter or dependency set.

**Impact:** Missing packaged Python produces a blocking backend failure. Release
verification requires exact policy versions, hashed runtime/model inventories,
native inference, PostgreSQL driver loading, and safety-environment assertions.

**Related files:** `app/main/pythonRuntime.ts`,
`scripts/build-desktop-runtime.ps1`,
`scripts/verify-desktop-runtime.mjs`

## 2026-07-24 - Desktop Secrets And Runtime Inventory Stay Isolated

**Decision:** The Electron-owned backend uses encrypted desktop secrets or
explicit process environment values, passes absent sensitive keys as empty, and
disables runtime bytecode writes. The runtime builder warms approved imports
before generating the manifest.

**Reason:** Desktop development must not silently inherit repository `.env`
credentials, and first launch must not create files that were absent from the
verified runtime inventory.

**Impact:** Legacy Python entry points retain their existing `.env` behavior.
Desktop startup falls back to in-memory storage when no explicit PostgreSQL DSN
is configured. With no explicit provider and no complete Capital.com
credential set, the desktop uses synthetic data so the owned backend remains
available without weakening execution defaults. An explicit `DATA_PROVIDER`,
`CAPITAL_ENV_FILE`, or complete encrypted Capital.com credential set remains
authoritative. Controlled warmup bytecode remains hashed and repeat runtime
verification is stable.

**Related files:** `app/main/backendProcessManager.ts`,
`scripts/build-desktop-runtime.ps1`, `docs/desktop/PACKAGING.md`

## 2026-07-21 - Measure Data Quality Always, Gate Inference Only By Explicit Opt-In

**Decision:** Emit candle-quality, aggregation, spread/provider, and stage-timing telemetry on every cycle, but leave fail-closed inference gating disabled unless `ENABLE_DATA_QUALITY_GATE=1` is explicitly configured.

**Reason:** Stale, gapped, outlier-contaminated, or partial data should not silently reach models. However, enabling a new block path changes recommendation frequency and requires shadow and out-of-sample evidence before promotion.

**Impact:** Enabled blocking produces deterministic HOLD abstentions without invoking model adapters or changing dynamic weights. No execution default, broker setting, schema, or historical replay freshness behavior changes.

**Related files:** `src/gold_signal_system/data_engine.py`, `src/gold_signal_system/pipeline.py`, `src/gold_signal_system/model_ensemble.py`, `tests/test_data_quality_gate.py`

## 2026-07-21 - Backtest Results Must Be Net Of Declared Trading Costs

**Decision:** The legacy backtest engine passes configured spread into pipeline risk checks and deducts spread, two slippage fills, and commission from simulated realized R.

**Reason:** Declaring cost settings without applying them materially overstates simulated results and prevents valid experiment comparison.

**Impact:** New reports expose gross R, cost R, net R, blocked-signal counts, and cost assumptions. Prior cost-free reports are not directly comparable and are not promotion evidence.

**Related files:** `src/gold_signal_system/backtesting.py`, `tests/test_data_quality_gate.py`, `docs/ai/EXPERIMENTS.md`

## 2026-07-21 - Canonical Tool-Neutral Agent Procedures With Thin Adapters

**Decision:** Keep verified project facts in `docs/ai/`, canonical reusable procedures in `.agents/skills/` and `.agents/workflows/`, and thin tool-specific adapters in `.claude/`, `.gemini/commands/`, and `.cursor/rules/`.

**Reason:** A shared procedural layer reduces duplicated context and inconsistent safety guidance while allowing each coding tool to use its native command/rule format. `docs/ai/HANDOFF.md` carries only active transfer state, while `TASK_LOG.md` remains the durable history.

**Impact:** Agents start with the memory index, current state, and active handoff, then load only relevant domain guidance. The checker enforces the core memory/handoff contract, scans instruction text for secret-like values without printing values, and warns when optional adapters are absent.

**Related files:** `docs/ai/README.md`, `docs/ai/HANDOFF.md`, `.agents/`, `.claude/`, `.gemini/commands/`, `.cursor/rules/`, `scripts/ai-memory/check-memory.mjs`

## 2026-07-21 - Keep Runtime And Large Model Artifacts Out Of Git

**Decision:** Publish application source, tests, documentation, schemas, scripts, lightweight model code/metadata, and reports while ignoring credentials, virtual environments, runtime/PostgreSQL state, dataset caches, and downloaded or trained model weights. Track `vendor/Kronos` as a submodule of its upstream repository.

**Reason:** Local runtime state can contain private or machine-specific data, and several generated model/database files exceed GitHub's normal per-file limit. The Kronos dependency already has an independent clean Git history.

**Impact:** The GitHub repository remains small and reproducible without exposing `.env` or runtime state. Fresh clones must run `git submodule update --init --recursive` and provision model artifacts locally.

**Related files:** `.gitignore`, `.gitmodules`

## 2026-07-15 - Re-authenticate Candle Polling Once After HTTP 401

**Decision:** Capital.com candle requests invalidate their cached REST session, authenticate again, and retry exactly once when the price endpoint returns HTTP 401. Authentication is considered successful only when both `CST` and `X-SECURITY-TOKEN` are present.

**Reason:** The candle provider previously cached `_authenticated=True` for the process lifetime. An expired or invalidated Capital.com session therefore stopped every later background signal cycle even while websocket prices and execution-account requests remained healthy.

**Impact:** Long-running signal generation can recover from an expired REST token without restarting the API. Persistent 401 responses still fail after one retry and remain visible through background-cycle health rather than looping indefinitely inside the provider.

**Related files:** `src/gold_signal_system/providers.py`, `tests/test_pipeline.py`

## 2026-07-03 - Filter Execution Orders By Existing Session JSON

**Decision:** The Execution Orders market-session filter reads the session from existing order/recommendation JSON instead of adding a new `execution_orders.market_session` column.

**Reason:** Executed rows already link to `trade_recommendations.raw_json.indicator_summary.session`, and some order rows store only the broker request in `request_json`. Filtering through existing JSON keeps historical rows usable and avoids a schema migration.

**Impact:** `/api/execution/orders` and `/api/execution/orders/export` accept `market_session`. PostgreSQL and in-memory storage both normalize legacy session labels to canonical XAUUSD sessions.

## 2026-07-03 - Compose Control Unit Session And Direction Gates

**Decision:** Control Unit direction permissions are stored as `allowed_directions` with BUY and SELL checked by default, and are evaluated after session checks with AND semantics.

**Reason:** Operators need to allow combinations such as `US_OVERLAP` plus SELL while blocking BUY or other sessions. Keeping direction permissions separate from sessions avoids a larger matrix UI while still requiring both conditions to pass.

**Impact:** Existing configs remain permissive because BUY and SELL default to enabled. Unchecking a direction blocks execution before broker submission for that signal direction.

## 2026-07-02 - Keep Capital.com Price Stream Alive With Provider Ping

**Decision:** The live price stream sends Capital.com's WebSocket `ping` service message on a configurable interval (`CAPITALCOM_STREAM_PING_SECONDS`, default 540 seconds) instead of relying on passive quote traffic or protocol-level pings.

**Reason:** Capital.com's public API documents a 10-minute WebSocket session lifetime unless the ping service is used. The dashboard needs provider-level keepalive and explicit reconnect status to avoid stale live prices.

**Impact:** Long-running dashboard sessions should keep receiving live ticks. If Capital.com interrupts streaming because of account/session changes, the worker reports `RECONNECTING` and retries instead of leaving the UI looking silently frozen.

## 2026-06-30 - External Env Files Must Be Explicit

**Decision:** Runtime config reads the project `.env` automatically but only imports external Capital.com/Kronos-compatible env files when `CAPITAL_ENV_FILE` is set.

**Reason:** A hardcoded machine-local path can silently import credentials or stale instrument/database settings and makes runtime behavior depend on one developer workstation.

**Impact:** Operators who relied on the old implicit external env path must set `CAPITAL_ENV_FILE` explicitly. Built-in defaults now use XAUUSD for `TRADING_INSTRUMENT` and `CAPITALCOM_EPIC`.

**Related files:** `src/gold_signal_system/config.py`, `README.md`, `tests/test_config_defaults.py`

## 2026-06-30 - Jordan Time Is Canonical For XAUUSD Sessions

**Decision:** Gold market-session classification uses `Asia/Amman` in `src/gold_signal_system/market_sessions.py`.

**Reason:** Control Unit execution gates, indicator tags, dynamic model context, and news labels need one shared source of truth and must not depend on server-local timezone or UTC-hour buckets.

**Impact:** Runtime sessions are `DAILY_BREAK`, `ASIA_LOW`, `LONDON_ACTIVE`, `US_OVERLAP`, and `NY_ACTIVE`; legacy session labels are accepted as aliases. `DAILY_BREAK` has highest priority and remains non-trading even if a payload attempts to enable it.

**Related files:** `src/gold_signal_system/market_sessions.py`, `src/gold_signal_system/execution_control.py`, `src/gold_signal_system/indicator_engine.py`, `tests/test_market_sessions.py`

## 2026-06-30 - Force Capital.com Account Selection Before Orders

**Decision:** Capital.com market execution must force `PUT /session` to the configured `CAPITAL_EXECUTION_ACCOUNT_NAME` immediately before `POST /positions`.

**Reason:** A cached client-side `_active_account` is not strong enough for broker execution safety if a long-running session drifts or account configuration changes.

**Impact:** Order submission performs an extra account-selection call, validates the selected account name/id, and redoes forced selection after 401 re-authentication.

**Related files:** `src/gold_signal_system/capital_execution.py`, `tests/test_capital_execution.py`, `tests/test_execution_control.py`
