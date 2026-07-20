# Database Rules

## Database Technology
*   **RDBMS**: PostgreSQL
*   **Driver**: `psycopg[binary]`
*   **Fallback**: In-Memory dict storage mechanism.

## Schema & Migration
*   **Schema Location**: `db/schema.sql`
*   **Namespacing**: The app uses the `newxau` schema to isolate tables.
*   **Migration**: No formal ORM (Alembic/Django) found. `scripts/init_db.py` handles raw SQL execution. Always use `CREATE TABLE IF NOT EXISTS`.

## Important Entities
*   `system_settings`: Key/value config state.
*   `candles`: OHLCV data.
*   `signals`: Produced trading signals.
*   `execution_orders`: Capital.com execution receipts.
*   `model_metrics`: Historical model accuracy.

## Query Rules
*   Always use parameterized queries (`%s` in psycopg) to prevent SQL Injection.
*   Never use f-strings for SQL query values.
*   Wrap multiple insert/updates in a transaction where atomicity is required.

## Dangerous Operations (Require Explicit Approval)
*   **NEVER DROP TABLES**. Use additive changes.
*   **NEVER TRUNCATE DATA**.
*   **DO NOT ALTER** existing columns in a way that drops data.

## Data Integrity
*   Use `ON CONFLICT` clauses (Upserts) heavily for idempotent retries.
*   Ensure foreign keys are respected if introduced.

## Current Default Instrument

New schema/default metadata should use `XAUUSD`. Existing rows are not rewritten automatically when defaults change; backfills or manual updates must be planned separately if historical rows need normalization.
