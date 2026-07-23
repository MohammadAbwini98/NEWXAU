---
name: capital-execution-safety
description: Review or modify NEWXAU Capital.com execution while preserving all execution safeguards.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash(git *), Bash(python *), Bash(node *)
---

# Capital Execution Safety

Follow `.agents/skills/capital-execution-safety/SKILL.md`. Read `docs/ai/SECURITY.md`, `docs/ai/RULES.md`, and `docs/ai/TESTING.md`. Never call a real broker. Run focused mocked tests, state whether eligibility changed and that no live request occurred, sync memory, and run the checker.
