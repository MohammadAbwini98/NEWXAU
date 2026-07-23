---
name: safe-database-changes
description: Review or modify NEWXAU PostgreSQL schema and persistence without destructive or unknown-database operations.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash(git *), Bash(python *), Bash(node *)
---

# Safe Database Changes

Follow `.agents/skills/safe-database-changes/SKILL.md`. Read `docs/ai/DATABASE.md`, `docs/ai/SECURITY.md`, and `docs/ai/TESTING.md`. Do not run migrations against unknown/production databases; explain affected tables, rollback, and fallback impact. Sync memory and run the checker.
