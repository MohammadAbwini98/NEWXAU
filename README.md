# XAUUSD Signal Recommendation System

This implementation follows the provided phase documents in `Changes/` and is built phase-by-phase end to end:

- Phase 1: Data Foundation (`data_engine.py`)
- Phase 2: Feature + Indicator Engine (`indicator_engine.py`)
- Phase 3: Model Ensemble (`model_ensemble.py`)
- Phase 4: Strategy Brain (`strategy_brain.py`)
- Phase 5: Entry / SL / TP Engine (`trade_plan_engine.py`)
- Phase 6: Risk Engine (`risk_engine.py`)
- Phase 7: Dashboard + APIs (`api.py`, `dashboard_static/index.html`)
- Phase 8: Backtesting (`backtesting.py`)
- Phase 9: Paper Trading (`paper_trading.py`)
- Phase 10: Controlled Live Safety (`live_control.py`)

## Setup

```powershell
pip install -r requirements.txt
```

## Runtime Modes

The system supports both local simulation and production-oriented runtime wiring.

### 1. Data Provider

- `DATA_PROVIDER=capitalcom` (default)
- `DATA_PROVIDER=csv` with `CANDLE_CSV_PATH=/path/to/candles.csv`
- `DATA_PROVIDER=synthetic` or `DATA_PROVIDER=mock` only for explicit local mock runs/tests
- `TRADING_INSTRUMENT=XAUUSD` sets the display/runtime instrument.

Capital.com configuration is compatible with the existing Kronos project env names:

- `CAPITAL_API_BASE_URL` or `CAPITALCOM_API_BASE`
- `CAPITAL_API_KEY` or `CAPITALCOM_API_KEY`
- `CAPITAL_IDENTIFIER` / `CAPITAL_EMAIL` or `CAPITALCOM_IDENTIFIER`
- `CAPITAL_PASSWORD` or `CAPITALCOM_PASSWORD`
- `CAPITAL_DEFAULT_EPIC` / `TRADING_PROVIDER_SYMBOL` or `CAPITALCOM_EPIC`
- `CAPITAL_DEFAULT_PRICE_SIDE` or `CAPITALCOM_PRICE_SIDE`
- `CAPITAL_USE_ENCRYPTED_PASSWORD`

The runtime automatically reads `.env` from the current directory. To import Capital.com/Kronos-compatible environment values from another file, set `CAPITAL_ENV_FILE` explicitly.

### 2. Model Artifacts

Baseline Python model artifacts are included in `models/` for all active advisors:

- `kronos.py`
- `tcn.py`
- `lightgbm.py`
- `patchtst.py`
- `cnn_lstm.py`
- `nhits.py`

These files satisfy the runtime artifact contract and are loaded by default. They are baseline adapters, not fine-tuned production weights. Replace them with trained artifacts when available.

The Kronos adapter can also use the upstream creator implementation from `shiyu-coder/Kronos` with the open `NeoQuasar/Kronos-mini` Hugging Face weights. Download/update those assets with:

```powershell
python scripts/download_kronos.py
```

By default `.env` points Kronos at:

```text
KRONOS_MODEL_ID=models/kronos_hf/Kronos-mini
KRONOS_TOKENIZER_ID=models/kronos_hf/Kronos-Tokenizer-2k
```

If the upstream assets or dependencies are unavailable, Kronos falls back to the local deterministic adapter and the rest of the ensemble continues running.

Set `MODEL_ARTIFACTS_DIR` to load artifacts from another directory.

Supported artifact formats:

- `kronos.joblib` / `kronos.pkl`
- `kronos.pt` / `kronos.pth`
- `kronos.onnx`
- `kronos.py` (plugin with `predict_proba` or `predict`)

The same naming pattern applies for each model key (`tcn`, `lightgbm`, `patchtst`, `cnn_lstm`, `nhits`).

If an artifact is missing or cannot be loaded, that model falls back to deterministic synthetic inference.

Check current artifact load status:

- `GET /api/models/artifacts`
- included in `GET /api/dashboard/summary` as `model_artifacts`

### 3. PostgreSQL Persistence

Set `POSTGRES_DSN` to persist live outputs to PostgreSQL tables from `db/schema.sql`.

The local `.env` sets:

```text
POSTGRES_SCHEMA=newxau
```

so NEWXAU stores its tables in a dedicated schema inside the Kronos database connection without colliding with Kronos tables.

Initialize or repair the database schema manually with:

```powershell
python scripts/init_db.py
```

`python scripts/run_api.py` also runs this initialization automatically before starting the dashboard.

If PostgreSQL is unavailable, the system automatically falls back to in-memory storage and keeps running.

### 4. Background Live Cycle Runner + Realtime

- `ENABLE_BACKGROUND_CYCLE_RUNNER=1` enables automatic periodic cycles.
- `LIVE_CYCLE_INTERVAL_SECONDS=300` runs every 5 minutes by default.
- `LIVE_CANDLE_LOOKBACK=900` controls provider fetch window.
- `LIVE_CYCLE_RETRY_ATTEMPTS=3` retries transient provider/network failures.
- `LIVE_CYCLE_RETRY_BACKOFF_SECONDS=2` sets retry backoff base.
- `WEBSOCKET_HEARTBEAT_SECONDS=30` controls WS heartbeat interval.

Web dashboard updates are now event-driven via websocket (`/ws/events`).
Live websocket price ticks are intentionally memory-only; durable records such as candles, signals, settings, health, execution, and backtests are persisted to PostgreSQL when `POSTGRES_DSN` is configured.

### 5. Capital.com Demo Execution

Signals can be executed as Capital.com demo trades through the dashboard `Execution` view or API endpoints. Execution is off by default and guarded by demo-only safety checks.

Minimum demo execution configuration:

```powershell
CAPITAL_ENV=demo
CAPITAL_EXECUTION_ENABLED=1
CAPITAL_EXECUTION_ACCOUNT_NAME=NEWXAU
CAPITAL_EXECUTION_DEMO_ONLY=1
CAPITAL_EXECUTION_DEFAULT_SIZE=0.01
CAPITAL_EXECUTION_MAX_SIZE=0.10
CAPITAL_EXECUTION_MAX_OPEN_POSITIONS=1
```

Manual execution:

```http
POST /api/execution/execute-latest
POST /api/execution/execute/{signal_id}
GET /api/execution/status
GET /api/execution/orders
```

Automatic execution after eligible signal cycles is available only when explicitly armed:

```powershell
CAPITAL_EXECUTION_AUTO_EXECUTE=1
```

Execution attempts are persisted in `execution_orders`; account snapshots are persisted in `execution_account_snapshots`. See `docs/capital_execution.md`.

### 6. Dynamic Model Weight Adaptation

- `ENABLE_DYNAMIC_MODEL_WEIGHTS=1` enables adaptive reweighting.
- `MIN_OBSERVATIONS_FOR_REWEIGHT=10` minimum outcomes before adaptation.

Per-model metrics and current adaptive weights are available at:

- `GET /api/models/performance`

## Start Dashboard

The dashboard is the main project entry point. Starting it also starts the API, live Capital.com candle fetching, model ensemble, Strategy Brain, risk checks, storage, and realtime websocket updates.

```powershell
python scripts/run_api.py
```

Open: `http://127.0.0.1:8000/`

The script stops any existing dashboard process on port `8000`, initializes the PostgreSQL schema if `POSTGRES_DSN` is configured, starts the API, and opens the dashboard automatically.

The first dashboard data request seeds a full live signal cycle when no recommendation exists yet. With `ENABLE_BACKGROUND_CYCLE_RUNNER=1`, live cycles continue on `LIVE_CYCLE_INTERVAL_SECONDS`.

## Run One Signal Cycle

```powershell
python scripts/run_cycle.py
```

This fetches candles from Capital.com. To run with generated mock candles:

```powershell
python scripts/run_cycle.py --mock
```

## Run Backtest

```powershell
python scripts/run_backtest.py
```

## Run Paper Trading Simulation

```powershell
python scripts/run_paper_trading.py
```

## Database Schema

PostgreSQL schema is provided in `db/schema.sql`. Existing databases can be upgraded with:

```powershell
python scripts/init_db.py
```
