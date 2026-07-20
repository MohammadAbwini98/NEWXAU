# Project Rules

Last updated: 2026-06-30

## Non-Negotiable Rules

- Do not invent project facts.
- Do not refactor unrelated code.
- Do not expose secrets.
- Preserve existing behavior unless explicitly asked to change it or the behavior is clearly stale/broken.
- Keep Capital.com automated execution off by default.
- Preserve `CAPITAL_EXECUTION_DEMO_ONLY=1` guard rails.
- Update AI memory after implementation work.

## Coding Style Rules

- Python uses type hints and `snake_case` functions/variables.
- Classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- Prefer existing helper APIs and local patterns.
- Add comments only where they clarify non-obvious behavior.

## Architecture Rules

- Preserve Data -> Indicators -> Models -> Strategy -> Trade Plan -> Risk -> Control Unit -> Execution separation.
- Keep PostgreSQL fallback to in-memory storage.
- Missing model artifacts must degrade to deterministic/safe inference rather than crashing the ensemble.
- XAUUSD session classification belongs in `market_sessions.py` and uses `Asia/Amman`.

## API Contract Rules

- FastAPI response shapes used by the dashboard should remain backward compatible.
- Use Pydantic models from `contracts.py` for structured API payloads where available.
- Background tasks should catch/log unexpected errors instead of crashing the Uvicorn process.

## Database Rules

- Never drop or truncate tables without explicit approval.
- Prefer additive/idempotent migrations.
- Keep timestamps stored in UTC; convert for display/session classification.
- Use parameterized SQL in `storage.py`.

## UI Rules

- Dashboard is vanilla HTML/JS in `src/gold_signal_system/dashboard_static/`.
- Do not introduce React/Vue/Angular unless explicitly requested.
- Keep empty/error states visible and understandable.

## Logging Rules

- Use Python `logging` for application code.
- Log useful context without API keys, passwords, tokens, cookies, or account credentials.

## Error Handling Rules

- External integrations should fail closed or degrade safely.
- Capital.com/API/network failures should produce clear errors and avoid duplicate unsafe execution.
- News/AI parsing failures should fall back to conservative rules where possible.

## Dependency Rules

- Do not add dependencies unless clearly needed.
- Prefer the current standard library/FastAPI/Pydantic/pytest stack.

## Documentation Rules

- Update `docs/ai/TASK_LOG.md` after every implementation task.
- Update current-state, features, architecture, commands, decisions, testing, or known-issues memory when relevant.
- Do not copy secrets into documentation.
