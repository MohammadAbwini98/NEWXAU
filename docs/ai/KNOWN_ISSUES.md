# Known Issues

Last updated: 2026-07-24

## Confirmed / Recurring Risks

- Local `.env` values can change test behavior when tests assume defaults. `tests/test_capital_execution.py` and `tests/test_execution_control.py` now set `CAPITAL_EXECUTION_ACCOUNT_NAME=NEWXAU` internally for their fake clients, but new tests should continue isolating broker/account env values.
- Broad pytest runs can be slow; run focused tests first for changed modules. A combined run including `tests/test_pipeline.py` timed out locally after 304 seconds on 2026-06-30; `tests --ignore=tests/test_pipeline.py` passed in 127 seconds and the targeted pipeline recommendation-shape test passed.
- Capital.com execution, candle/history, AI, and news integrations depend on network/session/config state and should be mocked in unit tests. Candle polling recovers once from an HTTP 401 by re-authenticating, but persistent authentication or broker failures still surface through background-cycle health.
- PostgreSQL Control Unit decision history requires `db/010_execution_control.sql`; run `python scripts/init_db.py` after deploying this change.
- Capital.com streaming can still reconnect when broker account/session changes are made, because the provider documents that streaming can fall off after `PUT /session`. The stream worker now backs off and reconnects, but long-running demo/live sessions should still be watched in the dashboard.
- Live price ticks and signal candle ingestion are separate paths. Capital.com websocket ticks may stay fresh while the background signal cycle stops refreshing the in-process candle store. `/api/system/health` exposes `background_cycle`; investigate if it becomes `STALE`, `ERROR`, or `STOPPED`, or if `last_success_at` stops advancing. The REST candle provider now recovers from one expired-session 401, but other repeated failures still require operator attention.
- With `ENABLE_DATA_QUALITY_GATE=1`, fewer than 20 valid candles still fail at
  indicator snapshot construction instead of returning a deterministic HOLD.
  The gate remains disabled by default and the failure does not reach broker
  execution, but this robustness edge should be resolved before promoting the
  gate.
- Local unsigned desktop packages are not release artifacts. Code signing,
  clean non-admin machine validation, installer/uninstaller testing, and parity
  acceptance remain mandatory promotion gates.
- The locally installed Node 18 runtime can run desktop tests and builds but
  fails Electron Builder when its CommonJS code loads the ESM-only hashing
  dependency. Use the required Node 22.12+ packaging toolchain.

## Manual Verification Needed

- Verify dashboard changes in the browser when editing `src/gold_signal_system/dashboard_static/index.html`.
- Verify Control Unit session and Kronos-rule toggles in the browser before relying on them for demo/live execution.
- Verify the dashboard Market Sessions panel at a real session boundary to confirm the server-provided active highlight advances after the next dashboard refresh/background signal event.
- Verify live/demo execution behavior with demo mode before enabling anything more permissive.
- Verify live price ticks in the browser during an open market after stream keepalive changes.
- Verify `/api/system/health.background_cycle` during an open market after restarting the API; it should report a healthy running worker and recent `last_success_at`.
- Treat full execution-order payload exports as operational data because they may include broker response details.
- Keep the legacy dashboard available for Paper Trading, diagnostics, advanced
  replay/charts/filters, exports, and legacy-only settings until the parity
  matrix records accepted replacements.
