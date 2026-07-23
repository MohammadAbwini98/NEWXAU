---
name: agent-handoff
description: Capture the exact active NEWXAU work state for another agent or human when pausing, blocking, or transferring work, without copying secrets.
---

# Agent Handoff

1. Inspect Git status (including untracked files), unstaged diff/statistics, staged diff/statistics, and relevant file contents.
2. Read `docs/ai/CURRENT_STATE.md` and the existing `docs/ai/HANDOFF.md`.
3. Update `docs/ai/HANDOFF.md` with the objective, completed work, in-progress work, blockers, next safe actions, changed files, performed verification, pending verification, and safety notes.
4. Never include `.env` values, raw DSNs, credentials, tokens, sessions, account details, or sensitive exports.
5. Update `docs/ai/TASK_LOG.md` only when meaningful work was completed.
6. Run `node scripts/ai-memory/check-memory.mjs`.
