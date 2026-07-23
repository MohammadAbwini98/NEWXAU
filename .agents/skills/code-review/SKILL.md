---
name: code-review
description: Use when reviewing code quality, architecture, bugs, maintainability, or refactoring in the NEWXAU codebase.
---

# Code Review Skill

When asked to review code, use this structured process:

## Review Process
1. Understand the goal of the modified code.
2. Ensure it follows `docs/ai/CODING_RULES.md` and `docs/ai/ARCHITECTURE.md`.
3. Check for obvious bugs, logical errors, or edge cases.
4. Verify tests exist or should be created.
5. Provide a summary of the findings before listing specific changes.

## Risk Checklist
- [ ] Does this break existing API contracts in `contracts.py`?
- [ ] Are exceptions handled gracefully without crashing the background runner?
- [ ] Is logging appropriate for production monitoring?
- [ ] Are secrets or sensitive data exposed in logs?

## Architecture Checklist
- [ ] Does this respect Data -> Indicators/SMC -> Models -> Strategy -> Trade Plan -> Risk -> Control Unit -> Execution decoupling?
- [ ] Does this add heavy dependencies that could be avoided?

## Bug Checklist
- [ ] Null references / missing dictionary keys handled safely?
- [ ] Correct integer/float casting for financial values?
- [ ] Timestamp timezone mismatches (everything should ideally be UTC)?

## Performance Checklist
- [ ] Are pandas dataframe operations vectorized (avoiding `iterrows`)?
- [ ] Are database operations optimized (indexed, batched)?

## Final Output Format
Provide your review as follows:
- **Summary**: Brief assessment.
- **Critical Issues**: Bugs or architecture violations.
- **Suggestions**: Code improvements and optimization.
- **Approved?**: Yes/No/With Changes.
