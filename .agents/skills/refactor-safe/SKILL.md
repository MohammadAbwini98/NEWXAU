---
name: refactor-safe
description: Refactor a scoped NEWXAU area without changing behavior, contracts, trading eligibility, persistence fallback, or runtime safety.
---

# Safe Refactor

1. Establish current behavior and focused tests before editing.
2. Define the smallest boundary and preserve public APIs, events, storage keys, side effects, and pipeline ordering.
3. Do not combine feature behavior changes with the refactor.
4. Preserve Capital.com, Control Unit, risk, model fallback, database fallback, and session safeguards.
5. Run before/after focused tests and inspect the diff for accidental behavior drift.
6. Sync memory only for real architecture/status changes and run the checker.
