# Production Hardening Master Prompt — Gold Signal Recommendation System

## Context

The Gold/XAUUSD signal recommendation system has already implemented the 12 improvement tasks, but the current state includes several MVP implementations:

- News provider is manual/mock-capable.
- Threshold optimization is simple grid scoring.
- Walk-forward backtesting uses the current pipeline but does not train real model artifacts.
- All modules are wired, but several require production hardening.

## Main Goal

Convert the MVP implementation into a production-grade, testable, reliable, measurable Gold signal recommendation platform.

The system must become:

1. Measurable
2. Auditable
3. Backtestable
4. Explainable
5. Safe for demo/live recommendation mode
6. Ready for real model retraining and real signal validation

## Implementation Rules

1. Do not break the existing working system.
2. Improve the current basecode incrementally.
3. Preserve backward compatibility where possible.
4. Add database migrations safely.
5. Add configuration flags for mock/manual/real providers.
6. Add clear logs for every important decision.
7. Add tests after each major module.
8. Update documentation after implementation.
9. Do not claim production readiness unless tests and wiring verification pass.
10. If something cannot be fully implemented now, create a clear TODO with exact reason and implementation path.

## Required Execution Order

Implement the tasks in this sequence:

1. Full implementation audit
2. News filter production hardening
3. Walk-forward backtesting upgrade
4. Threshold optimization upgrade
5. Signal validation hardening
6. Model performance hardening
7. Dynamic model weighting hardening
8. Entry/SL/TP plan scoring hardening
9. Market regime detection hardening
10. Multi-timeframe confirmation hardening
11. Dashboard production upgrade
12. Production monitoring hardening
13. Testing requirements
14. Final wiring verification

## Final Deliverables

After all tasks are complete, provide:

1. `docs/production_hardening_audit.md`
2. `docs/final_wiring_verification.md`
3. Updated database migrations
4. Updated backend services
5. Updated dashboard pages/components
6. Updated configuration files
7. Test coverage for critical modules
8. Sample generated signal with full explanation
9. Sample blocked signal with blocked reasons
10. Sample validated signal outcome
11. Sample walk-forward report
12. Sample threshold optimization report

## Important Rule

Start with the production hardening audit first. Do not start heavy refactoring before the audit report is created.
