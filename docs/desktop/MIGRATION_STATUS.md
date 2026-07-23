# NEWXAU desktop migration status

## Implemented

- Phase 0: pre-migration branch/tag, OpenAPI snapshot, REST inventory,
  WebSocket catalog, environment inventory, protected-file hashes, focused test
  evidence, and legacy/desktop screenshots.
- Phase 1: Electron + React + TypeScript scaffold with the AWKIT-derived frame,
  route shell, status bar, theme support, error boundary, single-instance lock,
  navigation lockdown, context isolation, and narrow preload bridge.
- Phase 2: `scripts/run_backend.py`, loopback-only dynamic port support,
  machine-readable readiness, runtime/resource roots, and desktop
  readiness/runtime/shutdown endpoints.
- Phase 3: desktop-owned Python process lifecycle, token generation, sanitized
  environment, logs, bounded restart, and graceful shutdown with kill fallback.
- Phase 4: bearer-protected desktop REST, token-protected WebSocket, exact
  configured CORS origin, sender validation, Windows `safeStorage`, and
  serialized settings/secret writes.
- Phase 5: typed API client, reconnecting event client, targeted refreshes, and
  event reconnect coverage.
- Phase 6: live Overview, Live Signal, System Health, and runtime status.
- Phases 7–9: Signals, Models, Indicators, Risk, Backtesting, Optimization,
  Replay, News, Execution, Control Unit, and protected Settings surfaces.
  Control Unit changes are explicit-save and protected from stale-response
  checkbox rollback.
- Phase 10 foundation: legacy UI retained; endpoint parity test and visual
  captures are checked in.
- Phase 12 foundation: Windows Python safety and Electron CI jobs.

## Deliberately gated

- Phase 11 installers are blocked until the private Windows Python runtime is
  staged and passes `npm run runtime:verify`.
- Code signing, clean-machine installer validation, and artifact promotion
  require release infrastructure outside this repository.
- The legacy dashboard must not be removed before explicit product acceptance.

## Safety posture

The Electron process never decides trading eligibility. The Python backend
remains authoritative. Desktop startup supplies `CAPITAL_EXECUTION_ENABLED=0`,
`CAPITAL_EXECUTION_AUTO_EXECUTE=0`, and `CAPITAL_EXECUTION_DEMO_ONLY=1` unless
an existing explicit environment value is present. No automated test contacts
Capital.com.
