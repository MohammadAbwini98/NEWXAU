# NEWXAU AI Memory Index

This directory is the shared source of truth for AI coding agents and human handoffs working on NEWXAU.

## Default Reading Order

1. `PROJECT_BRIEF.md` — product purpose and scope.
2. `CURRENT_STATE.md` — current verified behavior, incomplete work, and operational risks.
3. `HANDOFF.md` — active cross-agent transfer state.
4. `ARCHITECTURE.md` — pipeline, API, storage, model, execution, and runtime boundaries.
5. `RULES.md` — non-negotiable project and safety rules.
6. `COMMANDS.md` — repository-verified commands.
7. `TASK_LOG.md` — append-only work history.

## Read Only When Relevant

- `PROJECT_CONTEXT.md` — deeper domain and module context.
- `FEATURES.md` — feature inventory.
- `CODING_RULES.md` — Python conventions.
- `DATABASE.md` — PostgreSQL and persistence rules.
- `TESTING.md` — verification strategy.
- `SECURITY.md` — secret handling, API exposure, and trading safety.
- `KNOWN_ISSUES.md` — fragile areas and operational risks.
- `DECISIONS.md` — accepted decisions.
- `DEVELOPMENT_WORKFLOW.md` — agent workflow.

Additional task-specific records:

- `EXPERIMENTS.md` - reproducible baselines, candidate results, decisions, and rollback notes.
- `ENHANCEMENT_AUDIT_2026-07-21.md` - trading-intelligence reliability audit and prioritized roadmap.

## Critical Runtime Boundaries

- Current default instrument is `XAUUSD`.
- Trading execution is disabled by default.
- `CAPITAL_EXECUTION_DEMO_ONLY=1` must remain enforced.
- `DAILY_BREAK` is non-trading.
- Timestamps are stored in UTC; sessions are resolved in `Asia/Amman`.
- PostgreSQL failure must degrade to in-memory storage.
- Missing model artifacts must degrade safely.
- `vendor/Kronos` is an upstream submodule.

## Token Discipline

Start with:

- `AGENTS.md`
- this file
- `CURRENT_STATE.md`
- `HANDOFF.md`

Then read only documents and skills needed for the current task.

## Update Rules

- Append meaningful work to `TASK_LOG.md`.
- Update `CURRENT_STATE.md` only when verified state changed.
- Update `HANDOFF.md` when work is paused, blocked, or transferred.
- Update domain docs only when their facts changed.
- Never copy secrets, credentials, tokens, raw DSNs, account details, or sensitive broker payloads into Markdown.
