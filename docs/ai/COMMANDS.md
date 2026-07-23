# Commands

Last updated: 2026-07-23

Only list commands confirmed by repository evidence.

## Install

```powershell
pip install -r requirements.txt
```

## Development

```powershell
python scripts/run_api.py
python scripts/run_backend.py --host 127.0.0.1 --port 0
python scripts/run_cycle.py
python scripts/run_cycle.py --mock
python scripts/run_backtest.py
python scripts/run_paper_trading.py
python scripts/init_db.py
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest tests\test_desktop_runtime.py tests\test_desktop_contract_baseline.py tests\test_execution_control.py tests\test_capital_execution.py tests\test_market_sessions.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_market_sessions.py tests\test_execution_control.py -q
.\.venv\Scripts\python.exe -m pytest tests\test_capital_execution.py -q
npm test
```

## Compile / Syntax Check

```powershell
.\.venv\Scripts\python.exe -m compileall src scripts tests
```

## Desktop Build / Type Check

```powershell
npm ci
npm audit
npm run typecheck
npm run build
```

## Frontend

```powershell
npm run dev
```

The legacy dashboard remains vanilla HTML/JS served by FastAPI.

## Windows Packaging

Requires Node 22.12+ and a staged private runtime described in
`docs/desktop/PACKAGING.md`.

```powershell
npm run runtime:verify
npm run package:dir
npm run package:win
```

## AI Memory Check

```powershell
node --check scripts\ai-memory\check-memory.mjs
node scripts\ai-memory\check-memory.mjs
```

## Agent Handoff / Takeoff

- Claude Code commands: `/HANDOFF` and `/TAKEOFF`.
- Gemini/Antigravity commands: `/HANDOFF` and `/TAKEOFF`.
- Canonical procedures: `.agents/skills/agent-handoff/SKILL.md` and `.agents/skills/agent-takeoff/SKILL.md`.
