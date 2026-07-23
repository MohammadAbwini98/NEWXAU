---
name: feature-implementation
description: Implement a scoped NEWXAU feature using existing architecture, trading safeguards, minimal diffs, regression coverage, and focused verification.
---

# Feature Implementation

1. Read root instructions, the memory index, current state, handoff, architecture, rules, and task-relevant domain docs.
2. Inspect source and tests before editing; identify pipeline, API, storage, dashboard, model, and execution impacts.
3. Preserve broker, risk, Control Unit, session, storage-fallback, and model-fallback safeguards.
4. Make the smallest safe implementation and add focused regression tests.
5. Verify without real external-service calls.
6. Update the task log and only memory files whose facts changed.
7. Run the memory checker and report exact changes, tests, skips, and risks.
