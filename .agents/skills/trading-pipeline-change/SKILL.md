---
name: trading-pipeline-change
description: Review or modify NEWXAU signal-pipeline phases while preserving ordering, contracts, auditability, temporal integrity, and safe fallbacks.
---

# Trading Pipeline Change

1. Read architecture, rules, testing guidance, `pipeline.py`, relevant engines/contracts, and current tests.
2. Map inputs and outputs for every affected phase in Data -> Indicators/SMC -> Models -> Strategy -> Trade Plan -> Risk -> Control Unit -> Execution order.
3. Preserve contracts and downstream validation; review timestamp/timeframe alignment and look-ahead bias.
4. Preserve deterministic missing-artifact fallback and auditable model votes, decisions, trade levels, and risk results.
5. Run `tests/test_pipeline.py` plus focused related tests with external providers mocked.
6. State explicitly whether recommendation behavior changed; update memory and run the checker.
