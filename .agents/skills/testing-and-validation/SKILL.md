---
name: testing-and-validation
description: Use when adding tests, running validation, fixing failing tests, or verifying implementation in the tests/ directory.
---

# Testing and Validation Skill

When working on test coverage in `tests/`:

## Unit Test Rules
- Keep tests isolated. Mock out database connections and external API requests (e.g., Capital.com).
- Use `pytest` fixtures for common mock data (candles, signals).

## Integration Test Rules
- Test persistence with mocked/in-memory storage or an explicitly approved disposable PostgreSQL instance; do not substitute SQLite for PostgreSQL semantics.
- Mock all Capital.com, news, and AI provider calls.

## API Test Rules
- Use FastAPI's `TestClient` to validate HTTP endpoints.
- Check both successful inputs and malformed payloads.

## Frontend Test Rules
- Frontend tests are largely manual right now. See `frontend-ui-review` skill.

## Manual Validation Rules
- Provide safe manual instructions, but do not recommend live provider cycles, broker execution, or database migration unless the user explicitly authorizes them.

## Regression Checklist
- Run `python -m pytest tests/` before and after changes.
- Ensure no warnings are newly introduced.

## Final Validation Report Format
When finishing a testing task, output:
- **Tests Added/Modified**: List of test functions.
- **Pass/Fail Status**: Did they pass locally?
- **Manual Verification Steps**: What the user needs to do to verify in the browser/terminal.
