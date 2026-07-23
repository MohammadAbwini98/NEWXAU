---
name: performance-concurrency-review
description: Review NEWXAU performance and concurrency across FastAPI, background workers, ML/DataFrame compute, storage, and WebSockets using measurements.
---

# Performance and Concurrency Review

1. Distinguish event-loop work from synchronous ML/DataFrame computation and blocking I/O.
2. Review background retry/backoff, cancellation, task failures, WebSocket fan-out, and storage-call behavior.
3. Measure before making performance claims and record workload, environment, and baseline.
4. Preserve all risk, execution, storage-fallback, and provider-failure safeguards.
5. Prefer scoped, reversible changes and focused load/regression checks.
6. Report measured impact, limitations, and skipped production validation; sync memory and run the checker.
