# Gemini / Antigravity Instructions

Always read and follow:

@AGENTS.md
@docs/ai/README.md
@docs/ai/CURRENT_STATE.md
@docs/ai/HANDOFF.md

Use these additional files when relevant:

@docs/ai/PROJECT_CONTEXT.md
@docs/ai/ARCHITECTURE.md
@docs/ai/CODING_RULES.md
@docs/ai/TESTING.md
@docs/ai/DATABASE.md
@docs/ai/SECURITY.md

## Priority

1. Current user request
2. GEMINI.md
3. AGENTS.md
4. docs/ai/*.md
5. .agents/skills/*/SKILL.md when relevant
6. Existing codebase patterns

## Core Agent Rules

*   **Do not perform large rewrites without an explicit plan.**
*   **Always inspect code using grep/view_file before changing it.**
*   Keep the existing system architecture intact. Do not introduce new frameworks without permission.
*   Ensure the Capital.com live execution guards are preserved.
*   Always respect `POSTGRES_DSN` vs memory fallback behavior.

## Known Project Facts (Discovered via codebase review)
- This is an XAUUSD Signal Recommendation System named NEWXAU (PostgreSQL schema is normally `newxau`).
- Technologies: Python, FastAPI, Websockets, Uvicorn, PostgreSQL, Vanilla JS Dashboard.
- Machine Learning: TCN, LightGBM, PatchTST, CNN-LSTM, NHITS, Kronos.
- Scripts to run: `scripts/run_api.py`, `scripts/run_cycle.py`, etc.
