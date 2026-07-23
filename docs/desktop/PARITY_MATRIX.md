# Desktop parity matrix

| Legacy area | Desktop route | Backend contract | Status |
|---|---|---|---|
| Dashboard | Overview | dashboard, price, market hours, execution | Live |
| Live Signals | Live Signal | latest signal, price, risk | Live |
| Execution | Execution | status, orders, outcome refresh | Live/read-only execution |
| Control Unit | Control Unit | control config and session gates | Live/editable |
| Signal History | Signal History | signals history | Live |
| Model Ensemble | Models | votes, artifacts, weights, performance | Live |
| Indicators | Indicators | latest indicators | Live |
| Risk Center | Risk | risk status | Live |
| Backtesting | Backtesting | runs and safe synthetic run | Live |
| Optimization | Optimization | optimization runs | Live |
| Replay | Replay | latest signal/replay entry point | Initial live view |
| News | News Intelligence | news dashboard summary | Live |
| Health | System Health | health and desktop runtime | Live |
| Settings | Settings | desktop settings and encrypted secrets | Live |

The legacy HTML dashboard remains available at `/` and `/news`. “Live” means
the route is connected to the preserved backend contract; detailed chart-level
pixel parity remains part of acceptance review.
