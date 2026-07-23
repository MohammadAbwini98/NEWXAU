---
name: agent-takeoff
description: Resume NEWXAU work from the canonical handoff after verifying repository state, completed claims, and the next safe action.
---

# Agent Takeoff

1. Read `AGENTS.md`, `docs/ai/README.md`, `docs/ai/CURRENT_STATE.md`, and `docs/ai/HANDOFF.md`.
2. If the handoff has no active status or objective, do not invent work; proceed only from the current user request or wait for one.
3. Inspect tracked, staged, and untracked working-tree state and compare it with the handoff.
4. Verify completed claims from files and tests; do not inherit unverified assumptions.
5. Identify and continue only the next smallest safe action.
6. Preserve trading, database, model/submodule, and market-session safeguards.
7. Clear or replace stale handoff state after progress and run the memory checker.
