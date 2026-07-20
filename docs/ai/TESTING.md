# Testing & Validation

## Existing Framework
*   **Framework**: `pytest`.
*   **Configuration**: `pytest.ini` exists at root.
*   **Directory**: `tests/` folder.

## How to Run Tests
```powershell
python -m pytest tests/
```

Focused execution API/export validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py::CapitalExecutionApiTests::test_execution_orders_export_uses_full_dashboard_payload_shape -q
$env:CAPITAL_EXECUTION_ACCOUNT_NAME='NEWXAU'; .\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py -q
```

Focused Control Unit validation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_market_sessions.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_execution_control.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_dashboard_startup.py tests\test_execution_control.py -q
```

## Adding Tests
1. Create files in `tests/` named `test_*.py`.
2. Use mocking (`unittest.mock.MagicMock` or `patch`) for external API calls (e.g., Capital.com) and DB layers when writing unit tests.
3. Keep test execution fast.

## Validation Checklists

### Manual Validation
- Run `python scripts/run_cycle.py` and ensure a full signal is generated without stack traces.
- Open `http://127.0.0.1:8000/` and verify the dashboard loads, charts render, and websocket connects.

### API Validation
- Ensure new endpoints are registered in `api.py`.
- Verify input payloads with `Pydantic`.
- Verify response matches `contracts.py` definitions.
- For Execution Orders export, verify each item includes `execution_order`, `signal_detail`, `broker_response`, and `broker_confirm`.
- For Control Unit changes, verify `/api/execution/control`, `/api/execution/control/stats`, and Capital.com preflight blocking.

### Frontend Validation
- Check browser console for JS errors.
- Ensure responsive UI (does not break on resize).
- Verify websocket reconnection logic works if the server restarts.

### Database Validation
- Ensure new tables or columns are added to `db/schema.sql`.
- Run `python scripts/init_db.py` to confirm the schema applies cleanly.

### What if no tests exist for a feature?
*   Write them! Do not add new engines without at least a happy-path unit test.
