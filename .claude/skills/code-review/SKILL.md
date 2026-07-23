---
name: code-review
description: Review NEWXAU changes for correctness, architecture, maintainability, regressions, and safety.
allowed-tools: Read, Glob, Grep, Bash(git *), Bash(python *), Bash(node *)
---

# Code Review

Follow `.agents/skills/code-review/SKILL.md`. Read `docs/ai/ARCHITECTURE.md`, `docs/ai/RULES.md`, and task-relevant safety/testing memory. Run focused read-only verification when useful, report findings with file/line evidence, and run the memory checker only if documentation changes.
