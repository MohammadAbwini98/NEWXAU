# Desktop parity matrix

Allowed classifications are `Complete`, `Restricted by design`,
`Legacy fallback`, and `Not implemented`.

| Legacy area | Desktop route/capability | Classification | Notes |
|---|---|---|---|
| Dashboard summary | Overview | Complete | Current signal, price, market hours, execution state, and model summary use preserved backend contracts. |
| Live Signals | Live Signal | Complete | Latest recommendation, price, and risk context are live. |
| Execution status/orders | Execution | Complete | Status, recent orders, and safe outcome refresh are available. |
| Direct order submission | None | Restricted by design | The renderer mutation allowlist deliberately excludes order-submit endpoints; Python execution safeguards remain authoritative. |
| Non-dangerous execution management | Execution plus legacy dashboard | Legacy fallback | Advanced filters, detail inspection, and exports remain available in the legacy dashboard until ported and accepted. |
| Control Unit | Control Unit | Complete | Explicit-save configuration, session/direction gates, and stale-response protection are implemented. `DAILY_BREAK` remains a hard non-trading boundary. |
| Signal History | Signal History | Complete | Recent history and outcomes are connected. |
| Model Ensemble | Models | Complete | Votes, artifacts, weights, and performance are connected. |
| Indicators | Indicators | Complete | Latest indicator groups are connected. |
| Risk Center | Risk | Complete | Current risk status is connected. |
| Backtesting | Backtesting | Complete | Existing runs and the safe synthetic-run action are connected. |
| Optimization | Optimization | Complete | Optimization runs are connected. |
| Replay workflow | Replay plus legacy dashboard | Legacy fallback | The desktop provides the current replay entry view; complete step-through workflow remains in the legacy dashboard. |
| News Intelligence | News Intelligence | Complete | News dashboard summary is connected. |
| System Health | System Health | Complete | Backend health and desktop runtime state are connected. |
| Paper Trading | Legacy dashboard | Legacy fallback | No desktop paper-trading workflow is implemented yet. |
| Logs and diagnostics | Legacy dashboard and local log files | Legacy fallback | Desktop logs are redacted and retained locally; an accepted diagnostics/support-export UI is not implemented. |
| Detailed charts and filters | Legacy dashboard | Legacy fallback | Chart depth, advanced filtering, and pixel-level parity remain pending. |
| Exports and file handling | Legacy dashboard | Legacy fallback | Desktop-native save dialogs and support bundles are not implemented. |
| General settings | Settings plus legacy dashboard | Legacy fallback | Desktop appearance/startup and encrypted secrets are implemented; model/risk settings available only in the legacy dashboard remain there. |

## Cutover policy

The legacy HTML dashboard remains available at `/` and `/news`. It is the
supported fallback for every row classified `Legacy fallback`.

The legacy dashboard may be removed only after:

1. every row is `Complete` or explicitly `Restricted by design`;
2. desktop charts, filters, replay, exports, Paper Trading, diagnostics, and
   non-dangerous execution management have acceptance evidence;
3. settings parity has been audited;
4. explicit product cutover approval is recorded.

Direct order submission is not a parity defect. Its absence from the Electron
renderer is an intentional safety boundary.
