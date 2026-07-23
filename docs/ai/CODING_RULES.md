# Coding Rules

## Naming Conventions
*   **Python Variables/Functions**: `snake_case`
*   **Python Classes**: `PascalCase`
*   **Constants**: `UPPER_SNAKE_CASE`
*   **Files**: `snake_case.py`

## Folder Conventions
*   `src/gold_signal_system/`: Put all core domain logic here.
*   `src/gold_signal_system/dashboard_static/`: All frontend files.
*   `scripts/`: Runnable top-level commands. Do not put domain logic here, just orchestration.
*   `tests/`: Standard pytest suite.

## Module/Architecture Rules
*   **No Circular Imports**: Keep domains isolated. Use `contracts.py` or simple types for shared definitions.
*   **Pipeline Isolation**: E.g., `IndicatorEngine` should not know about `ModelEnsemble`. Only the pipeline orchestrator (`pipeline.py`) binds them together.

## Error Handling
*   FastAPI endpoints should return clean `HTTPException` with meaningful details.
*   Background tasks should catch broad exceptions (`Exception as e`), log them, and back off, rather than crashing the whole system.
*   Model failures must degrade gracefully (fallback to deterministic/null generation).

## Logging
*   Use the standard `logging` module.
*   Log `INFO` for lifecycle events, `WARNING` for degraded state/fallback, `ERROR` for unexpected crashes.

## Async / Concurrency
*   Use `async def` for FastAPI endpoints and I/O bound logic.
*   Use `def` for pure compute functions (pandas, indicators, ML).

## Dependency Rules
*   Stick to standard libraries + `requirements.txt`. Do not add heavy dependencies unless strictly required.
*   Avoid over-engineering. E.g., do not add Redis or Celery; use existing `asyncio` and `psycopg` infrastructure.
