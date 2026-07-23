---
name: bug-fix
description: Trace and fix NEWXAU defects with minimal changes, regression coverage, safe fallbacks, and focused verification.
---

# Bug Fix

1. Read current state, handoff, known issues, architecture, rules, and relevant tests.
2. Reproduce safely or trace the root cause, then classify the affected boundary.
3. Patch the smallest safe area; do not weaken fallbacks or execution safeguards to hide symptoms.
4. Add a regression test and run focused verification.
5. Update the task log and known issues when relevant, then run the memory checker.
