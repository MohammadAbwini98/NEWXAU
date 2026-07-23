# Commands

Last updated: 2026-07-21

Only list commands confirmed by repository evidence.

## Install

```powershell
pip install -r requirements.txt
```

## Development

```powershell
python scripts/run_api.py
python scripts/run_cycle.py
python scripts/run_cycle.py --mock
python scripts/run_backtest.py
python scripts/run_paper_trading.py
python scripts/init_db.py
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest tests\test_market_sessions.py tests\test_execution_control.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py -q
```

## Compile / Syntax Check

```powershell
.\.venv\Scripts\python.exe -m compileall src scripts tests
```

## Lint / Type Check

No dedicated lint/type-check command is configured in the repository.

## Frontend

There is no `package.json`; the dashboard is vanilla HTML/JS served by FastAPI.

## AI Memory Check

```powershell
node --check scripts\ai-memory\check-memory.mjs
node scripts\ai-memory\check-memory.mjs
```

## Agent Handoff / Takeoff

- Claude Code commands: `/HANDOFF` and `/TAKEOFF`.
- Gemini/Antigravity commands: `/HANDOFF` and `/TAKEOFF`.
- Canonical procedures: `.agents/skills/agent-handoff/SKILL.md` and `.agents/skills/agent-takeoff/SKILL.md`.
