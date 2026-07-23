---
name: docs-sync
description: Synchronize NEWXAU documentation and AI memory with verified repository behavior after implementation, architecture, command, or safety changes.
---

# Documentation Sync

1. Inspect source, tests, status, and diffs; do not document unverified assumptions.
2. Update `TASK_LOG.md` append-only and only other memory files whose facts changed.
3. Keep root instructions concise and point detailed truth to `docs/ai/`.
4. Never copy secrets, raw DSNs, tokens, sessions, account details, or sensitive broker payloads.
5. Run `node scripts/ai-memory/check-memory.mjs` and report updated files and remaining unknowns.
