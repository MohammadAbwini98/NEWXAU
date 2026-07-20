# Decisions

Last updated: 2026-07-21

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
