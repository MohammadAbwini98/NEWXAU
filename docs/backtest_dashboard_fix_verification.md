# Backtest Dashboard Fix Verification

## What Was Broken

The dashboard only called `GET /api/backtest/summary`, and that endpoint read process-local memory. `GET /api/backtests` also read the in-memory `walk_forward_service.runs` list. After restarting the API, completed backtest objects disappeared unless report files were manually inspected.

Live signal history was persisted, but backtest and walk-forward history was not a durable dashboard data source.

## What Was Fixed

- Backtest and walk-forward runs now have durable storage methods.
- `POST /api/backtests/run` executes a normal backtest or walk-forward backtest.
- Completed runs save summary, trades, metrics, folds, and report metadata.
- `GET /api/backtests` reads persisted run history.
- `GET /api/backtest/summary` returns the latest completed run or a clear empty state.
- API startup imports report folders that are missing from the database.
- The dashboard Backtesting page now has a run modal, metrics cards, run history, fold results, trades, and report links.

## Endpoints Added Or Updated

- `POST /api/backtests/run`
- `POST /api/backtests/walk-forward/start`
- `GET /api/backtests`
- `GET /api/backtest/summary`
- `GET /api/backtests/{run_id}`
- `GET /api/backtests/{run_id}/windows`
- `GET /api/backtests/{run_id}/signals`
- `GET /api/backtests/{run_id}/trades`
- `GET /api/report-file?path=...`

## Database Tables Added Or Upgraded

- `backtest_runs`
- `backtest_trades`
- `backtest_metrics`
- `walk_forward_runs`
- `walk_forward_folds`
- `walk_forward_reports`

Migration file: `db/004_backtest_persistence.sql`.

## Report Locations

Walk-forward reports:

```text
reports/walk_forward/{run_id}/summary.json
reports/walk_forward/{run_id}/folds.csv
reports/walk_forward/{run_id}/trades.csv
reports/walk_forward/{run_id}/metrics.json
reports/walk_forward/{run_id}/recommendations.md
```

Normal backtest reports:

```text
reports/backtests/{run_id}/summary.json
reports/backtests/{run_id}/trades.csv
reports/backtests/{run_id}/metrics.json
reports/backtests/{run_id}/recommendations.md
```

## Run From API

```http
POST /api/backtests/run
```

Example body:

```json
{
  "run_type": "WALK_FORWARD",
  "instrument": "XAUUSD",
  "timeframe": "5m",
  "initial_balance": 10000,
  "risk_percent": 1.0,
  "model_mode": "MOCK_FOR_TEST_ONLY"
}
```

The endpoint currently runs synchronously and returns `COMPLETED` or `FAILED` with the `run_id`.

## Run From Dashboard

Open the Backtesting sidebar item, click `Run Walk-Forward Backtest`, select the configuration, and submit. The dashboard refreshes:

- latest summary
- run history
- fold results
- trades table
- report links

## Restart Loading

On API startup, the system:

1. Counts existing runs in PostgreSQL.
2. Scans `reports/backtests/`.
3. Scans `reports/walk_forward/`.
4. Imports missing report summaries without duplicating existing `run_id` records.

## Strategy Brain Connection

The backtest engine calls `system.run_signal_cycle(...)`, which uses the same production indicator, model ensemble, Strategy Brain, entry plan, and risk path used by live recommendations.

Each run stores and displays `model_mode`:

- `STORED_PREDICTIONS`
- `LIVE_INFERENCE`
- `MOCK_FOR_TEST_ONLY`

## Known Limitations

- Backtests currently execute synchronously.
- Historical date range fetching is not yet connected to Capital.com candle history inside the run endpoint; when no candles are provided, synthetic candles are used and the run is labeled `MOCK_FOR_TEST_ONLY`.
- Walk-forward folds reuse the current backtest engine and do not yet retrain model artifacts per fold.

## Next Improvements

- Add an async job queue and polling endpoint for long backtests.
- Fetch historical Capital.com candles for the requested date range.
- Add stored prediction replay mode for model-consistent historical runs.
- Add downloadable ZIP bundles for full report folders.
