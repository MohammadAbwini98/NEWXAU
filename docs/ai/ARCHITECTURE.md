# System Architecture

## High-Level Architecture
This is a modular, pipeline-driven trading application. Data flows sequentially through discrete phases.

```mermaid
graph TD;
    DataEngine-->IndicatorEngine;
    IndicatorEngine-->ModelEnsemble;
    ModelEnsemble-->StrategyBrain;
    StrategyBrain-->TradePlanEngine;
    TradePlanEngine-->RiskEngine;
    RiskEngine-->ExecutionControl;
    ExecutionControl-->Storage/Execution;
```

## Backend Structure
*   **Language**: Python 3.10+
*   **Framework**: FastAPI + Uvicorn
*   **Concurrency**: Async/await for APIs and websocket broadcasts; synchronous processing for heavy ML/DataFrame math.
*   **Event Flow**: `event_bus.py` provides pub/sub. Background runner emits cycle updates to the bus, which the websocket pushes to clients.

## Frontend Structure
*   Vanilla JS / HTML / CSS located in `src/dashboard_static/`.
*   Located in `src/gold_signal_system/dashboard_static/`.
*   Connects to `/api` endpoints for historical REST queries.
*   Connects to `/ws/events` for live streaming updates.

## Database / Data Layer
*   **Engine**: PostgreSQL.
*   **Schema**: Uses `newxau` schema space to avoid collision with standard Kronos schema.
*   **ORM**: Raw SQL via `psycopg`, managed centrally in `storage.py`.
*   **Fallback**: An in-memory dict structure mimics the DB if PostgreSQL fails to connect.
*   **Settings**: Runtime dashboard settings are persisted through `system_settings`.
*   **Execution Control Audit**: Control Unit decisions are stored in `execution_control_decisions`.

## Execution Control Flow
1. Dashboard writes Control Unit config through `/api/execution/control`.
2. Config is validated by `ExecutionControlConfig` and stored as `execution_control.active`.
3. `CapitalExecutionService` calls `ExecutionControlService.evaluate()` during preflight.
4. Disabled sessions or failed Kronos/ensemble relation gates return a normal BLOCKED execution result before any broker submission.
5. Decision stats are served through `/api/execution/control/stats`.

## Gold Market Session Flow
*   `market_sessions.py` is the canonical XAUUSD session schedule.
*   Timestamps are classified after conversion to `Asia/Amman`; server-local timezone is not used.
*   Runtime sessions are `DAILY_BREAK`, `ASIA_LOW`, `LONDON_ACTIVE`, `US_OVERLAP`, and `NY_ACTIVE`.
*   `DAILY_BREAK` has highest priority and is a hard non-trading session for the Control Unit.
*   Indicator snapshots, Control Unit fallback classification, dynamic model-weight context, and rules-based news labels consume this shared resolver.

## Background Workers
*   Triggered in `api.py` via `asyncio.create_task(run_background_cycle_loop())` if `ENABLE_BACKGROUND_CYCLE_RUNNER=1`.
*   The cycle runner handles polling, pipeline execution, and event emission.

## Deployment / Runtime Flow
1. Load environment variables.
2. Initialize DB schema (`scripts/init_db.py`).
3. Boot FastAPI server.
4. Clients connect, prompting historical data fetch and establishing websocket.
5. Cycle Runner polls API -> generates signals -> stores to DB -> executes (if armed) -> emits WS event.
