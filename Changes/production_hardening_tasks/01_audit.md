# Task 01 — Full Implementation Audit

## Goal

Review the whole codebase and identify every area that is not production-ready.

The objective is to clearly separate:

- Fully implemented production modules
- MVP modules
- Mock/manual/placeholder modules
- Missing integrations
- Missing database persistence
- Missing dashboard visibility
- Missing tests

## What to Review

Review all modules related to:

- Signal generation
- Signal validation
- Model ensemble
- Model performance tracking
- Dynamic model weighting
- Strategy Brain
- Entry/SL/TP engine
- Risk engine
- News filter
- Market regime detection
- Multi-timeframe confirmation
- Walk-forward backtesting
- Threshold optimization
- Dashboard APIs
- Database persistence
- Production monitoring

## Required Audit Categories

Identify every area that is:

- Mocked
- Manual-only
- Placeholder
- Hardcoded
- Not fully wired
- Not tested
- Not persisted in database
- Not shown in dashboard
- Not used by the Strategy Brain
- Producing fake or incomplete metrics

## Output File

Create:

```text
/docs/production_hardening_audit.md
```

## Required Report Format

For each issue, use this format:

```text
Module:
Current status:
Problem:
Production impact:
Recommended fix:
Files affected:
Priority: Critical / High / Medium / Low
```

## Wiring Expectations

The audit must trace each module from input to output:

```text
Market Data
  -> Indicators
  -> Models
  -> Model Normalizer
  -> Strategy Brain
  -> Entry/SL/TP Engine
  -> Risk Engine
  -> Final Signal
  -> Database
  -> Dashboard
  -> Validation Engine
  -> Performance Tracking
```

## Acceptance Criteria

- Audit file is created.
- All MVP/mock/manual areas are clearly listed.
- Each issue has priority and affected files.
- No production-hardening implementation starts before this report exists.
