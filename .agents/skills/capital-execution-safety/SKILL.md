---
name: capital-execution-safety
description: Review or modify NEWXAU Capital.com execution and Control Unit logic while preserving every eligibility, demo, account, and idempotency safeguard.
---

# Capital Execution Safety

1. Read `docs/ai/SECURITY.md`, `docs/ai/RULES.md`, execution/control code, configuration, contracts, and focused tests.
2. Confirm execution remains disabled by default and `CAPITAL_EXECUTION_DEMO_ONLY=1` remains enforced.
3. Review idempotency, forced account selection/validation, open-position limits, direction, status, confidence, risk, expiry, live-price freshness/deviation, and Control Unit gates.
4. Reject any silent broadening of execution eligibility.
5. Mock every network call; never authenticate to or call a real broker.
6. Run focused execution, Control Unit, and stream tests as applicable.
7. State whether eligibility changed and explicitly state that no live broker request occurred; sync memory and run the checker.
