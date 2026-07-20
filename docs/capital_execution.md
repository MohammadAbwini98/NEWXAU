# Capital.com Demo Execution

## What Was Added

The system can now submit eligible Strategy Brain signals to Capital.com as demo trades through a dedicated execution layer.

The execution path is:

```text
Signal Recommendation
-> execution safety gates
-> Capital.com demo account selection
-> open-position limit check
-> market order request
-> broker confirmation polling
-> persisted execution audit
-> dashboard execution view
```

## Safety Gates

Execution is blocked unless all of these are true:

- `CAPITAL_EXECUTION_ENABLED=1`
- The configured Capital.com API base is the demo endpoint when `CAPITAL_EXECUTION_DEMO_ONLY=1`
- The selected account name/id matches `CAPITAL_EXECUTION_ACCOUNT_NAME`, default `NEWXAU`
- The recommendation signal is `BUY` or `SELL`
- The recommendation status is allowed, default `RECOMMENDED`
- `risk_status` is `PASSED`
- Entry price, stop loss, and TP1 are present
- The signal is not expired
- The latest price is not stale
- Current price is within `CAPITAL_EXECUTION_MAX_PRICE_DEVIATION`
- Open positions for the configured epic are below `CAPITAL_EXECUTION_MAX_OPEN_POSITIONS`, default `1`
- The signal was not already submitted

## Required Environment

The Capital.com credentials are shared with the existing candle and websocket integrations:

```powershell
CAPITAL_ENV=demo
CAPITALCOM_API_KEY=...
CAPITALCOM_IDENTIFIER=...
CAPITALCOM_PASSWORD=...
CAPITALCOM_EPIC=XAUUSD
```

Execution-specific settings:

```powershell
CAPITAL_EXECUTION_ENABLED=1
CAPITAL_EXECUTION_ACCOUNT_NAME=NEWXAU
CAPITAL_EXECUTION_DEMO_ONLY=1
CAPITAL_EXECUTION_DEFAULT_SIZE=0.01
CAPITAL_EXECUTION_MAX_SIZE=0.10
CAPITAL_EXECUTION_MAX_OPEN_POSITIONS=1
CAPITAL_EXECUTION_MAX_PRICE_DEVIATION=2.0
```

Optional auto execution after every eligible signal cycle:

```powershell
CAPITAL_EXECUTION_AUTO_EXECUTE=1
```

Auto execution is intentionally off by default. Manual execution from the dashboard is available after `CAPITAL_EXECUTION_ENABLED=1`.

## API Endpoints

```http
GET /api/execution/status
GET /api/execution/orders
POST /api/execution/execute-latest
POST /api/execution/execute/{signal_id}
```

`POST /api/execution/execute-latest` executes the latest persisted signal if it passes all gates.

## Persistence

Migration:

```text
db/006_capital_execution.sql
```

Tables:

```text
execution_orders
execution_account_snapshots
```

Every blocked, failed, submitted, confirmed, or rejected attempt is stored with request/response JSON and broker identifiers.

## Dashboard

The dashboard has an `Execution` sidebar view showing:

- execution enabled/disabled state
- demo-only mode
- account name
- configured epic
- latest account snapshot
- recent execution orders
- manual `Execute Latest Demo Signal` button

## Known Limitations

- Position sizing currently uses configured broker size (`CAPITAL_EXECUTION_DEFAULT_SIZE`) with min/max/step limits. Account-equity risk sizing can be added once Capital.com market contract details are reliably available.
- TP1 is sent as the broker profit level. TP2/TP3 remain in the signal audit and can be used later for partial-close management.
- The implementation does not submit live-account trades while demo-only mode is enabled.
