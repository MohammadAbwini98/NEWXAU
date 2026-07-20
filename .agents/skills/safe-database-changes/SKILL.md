---
name: safe-database-changes
description: Use when touching database schema, migrations, SQL queries, ORM entities, repositories, or persistence logic in storage.py or init_db.py.
---

# Safe Database Changes Skill

When dealing with database operations or modifying `storage.py` and `init_db.py`, follow these strict rules:

## Strict Safety Rules
1. **Never drop tables** without explicit user approval.
2. **Never truncate data** without explicit user approval.
3. **Never run destructive SQL automatically**. Always provide the SQL and wait for the user to run it.
4. Prefer **additive migrations** (e.g., adding columns with defaults instead of renaming or deleting them).
5. Always explain the **rollback plan**.
6. Always identify the **affected tables/entities**.

## Reviewing SQL
- Ensure parameterized queries (`%s` in psycopg) are used everywhere to prevent SQL injection.
- Ensure `ON CONFLICT` is used correctly for idempotency.
- Verify that `POSTGRES_SCHEMA` (usually `newxau`) is referenced correctly in new queries.
