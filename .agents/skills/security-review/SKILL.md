---
name: security-review
description: Audit NEWXAU secrets, API exposure, execution authorization, SQL, logging, dependencies, untrusted content, broker payloads, and unsafe defaults.
---

# Security Review

1. Review secret loading/storage, tracked files, logs, exports, and error responses without printing secret values.
2. Review API exposure/authentication and authorization around execution-capable endpoints.
3. Verify execution remains disabled by default and demo-only safeguards cannot be bypassed.
4. Review parameterized SQL, schema validation, migration safety, and PostgreSQL fallback.
5. Review dependencies, untrusted news/AI input, broker payload exposure, and dangerous local artifacts.
6. Rank findings by exploitability and impact; distinguish verified issues from hardening suggestions.
7. Use only safe read-only checks, update memory when facts change, and run the checker.
