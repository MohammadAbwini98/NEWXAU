---
name: pr-review
description: Review NEWXAU pull-request changes for correctness, regressions, architecture violations, trading safety, security, and missing verification.
---

# Pull Request Review

1. Read the request, diff, root instructions, current state, and task-relevant domain rules.
2. Prioritize actionable bugs, safety regressions, security issues, contract breaks, and missing tests over style preferences.
3. Verify pipeline ordering, execution eligibility, PostgreSQL fallback, model fallback, session/timezone behavior, and dashboard compatibility when affected.
4. Cite exact files and lines, explain impact and reproduction, and avoid unsupported findings.
5. Report residual risks and tests not run; do not modify code unless explicitly asked.
