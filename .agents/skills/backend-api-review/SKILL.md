---
name: backend-api-review
description: Use when modifying FastAPI endpoints, controllers, services, DTOs, validation, integrations, workers, or backend business logic.
---

# Backend API Review Skill

When modifying `api.py`, background tasks, or `contracts.py`:

## API Safety Rules
- Do not expose sensitive endpoints (e.g., executing trades) without checking the demo/safety guards.
- Ensure websocket broadcasts only send safe public data, not server secrets.

## DTO Validation Rules
- All incoming and outgoing data must be validated using `Pydantic` models defined in `contracts.py`.

## Error Handling Rules
- Return standard HTTP 4xx for bad input, 5xx for server errors.
- Never crash the main Uvicorn loop. Catch exceptions in background tasks.

## Logging Rules
- Log requests at `DEBUG` or `INFO`. Log failures at `ERROR` with stack traces hidden from the client response.

## Transaction Rules
- API calls that modify database state must cleanly rollback if an error occurs mid-flight.

## Integration Rules
- When modifying Capital.com API logic, use mocked clients and preserve `CAPITAL_EXECUTION_DEMO_ONLY=1`; never access a real provider during validation.

## Backward Compatibility Rules
- Do not break existing API contracts that the frontend dashboard relies on. If a field changes, deprecate the old one slowly.
