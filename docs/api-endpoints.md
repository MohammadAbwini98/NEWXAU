# API Endpoints

Core dashboard:

- `GET /`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/current-signal`
- `GET /api/price/latest`
- `GET /ws/events`

Signals and replay:

- `GET /api/signals/latest`
- `GET /api/signals/recent`
- `GET /api/signals/history`
- `GET /api/signals/outcomes`
- `GET /api/signals/outcomes/summary`
- `GET /api/signals/{id}`
- `GET /api/signals/{id}/snapshot`
- `GET /api/signals/{id}/outcome`
- `GET /api/signals/{id}/regime`
- `GET /api/signals/{id}/timeframe-confirmation`
- `GET /api/signals/{id}/entry-plans`
- `GET /api/signals/{id}/selected-plan`
- `GET /api/signals/{id}/replay`
- `POST /api/signals/run`
- `POST /api/signals/validate-pending`

Models:

- `GET /api/models/latest-votes`
- `GET /api/models/artifacts`
- `GET /api/models/performance`
- `GET /api/models/performance/summary`
- `GET /api/models/performance/{modelName}`
- `GET /api/models/performance/by-regime`
- `GET /api/models/performance/confidence-calibration`
- `GET /api/models/weights/current`
- `GET /api/models/weights/history`
- `POST /api/models/weights/recalculate`
- `PUT /api/models/weights/profile/{modelName}`

Market, news, and health:

- `GET /api/market/regime/current`
- `GET /api/market/regime/history`
- `GET /api/market/timeframes/current`
- `GET /api/news/upcoming`
- `GET /api/news/current-risk`
- `POST /api/news/sync`
- `GET /api/system/health`
- `GET /api/system/health/events`
- `POST /api/system/health/check-now`

Backtesting and optimization:

- `GET /api/backtest/summary`
- `POST /api/backtests/walk-forward/start`
- `GET /api/backtests`
- `GET /api/backtests/{id}`
- `GET /api/backtests/{id}/windows`
- `GET /api/backtests/{id}/signals`
- `POST /api/optimization/start`
- `GET /api/optimization/runs`
- `GET /api/optimization/runs/{id}`
- `GET /api/optimization/runs/{id}/candidates`
- `GET /api/strategy/profiles/active`
- `POST /api/strategy/profiles/{id}/activate`
- `POST /api/strategy/profiles/rollback`
