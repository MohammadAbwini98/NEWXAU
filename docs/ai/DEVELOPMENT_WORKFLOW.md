# Development Workflow

Last updated: 2026-06-30

## How Agents Should Start Work

1. Read `AGENTS.md`.
2. Read relevant `docs/ai/` files.
3. Inspect the relevant source files before changing them.
4. Run focused baseline validation when practical.
5. Confirm current behavior with tests, scripts, or static review before modifying production paths.

## How To Make Safe Changes

- Keep diffs small and scoped.
- Preserve the existing pipeline boundaries.
- Prefer existing helpers and storage/API patterns over new abstractions.
- Do not rewrite `pipeline.py` or `storage.py` wholesale.
- Avoid touching secrets or machine-specific config.
- Keep Capital.com execution off by default and preserve demo-only guard rails.
- Add or update focused tests for behavior changes.

## How To Finish A Task

1. Run relevant tests/checks.
2. Update `docs/ai/TASK_LOG.md`.
3. Update other memory files when behavior, commands, architecture, or risks changed.
4. Run `node scripts\ai-memory\check-memory.mjs`.
5. Summarize changed files, validations, and remaining risks.

## Common Validation Path

```powershell
.\.venv\Scripts\python.exe -m compileall src scripts tests
.\.venv\Scripts\python.exe -m pytest <focused tests> -q
node scripts\ai-memory\check-memory.mjs
```

Broad test runs can be slow on this repo, so focused tests should be run first for touched modules.
