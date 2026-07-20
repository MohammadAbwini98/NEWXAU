# Cross-Agent Instructions (AGENTS.md)

This file contains the core facts and rules for ChatGPT/Codex, Gemini, Claude, and other coding agents working on this project.

## Project Overview

*   **Name**: Signal Recommendation System (NEWXAU / ETHUSD).
*   **Goal**: Provides automated trading signals, backtesting, paper trading, and Capital.com live execution integration.
*   **Key Components**: Data Engine, Indicator Engine, Model Ensemble, Strategy Brain, Trade Plan Engine, Risk Engine, API/Dashboard, Storage, and Capital.com execution.

## Tech Stack

*   **Backend**: Python, FastAPI, Uvicorn, websockets.
*   **Data Science/ML**: pandas, numpy, scikit-learn, PyTorch, LightGBM, HuggingFace Hub, ONNX.
*   **Database**: PostgreSQL (`psycopg`), falling back to in-memory if unavailable.
*   **Frontend**: Vanilla HTML/JS (`src/dashboard_static/`).

## Repository Structure

*   `src/gold_signal_system/`: Main application code (`api.py`, `pipeline.py`, `storage.py`, `capital_execution.py`, etc.).
*   `src/dashboard_static/`: Frontend web UI.
*   `scripts/`: Execution scripts (`run_api.py`, `run_cycle.py`, `init_db.py`, etc.).
*   `tests/`: Pytest test suite.
*   `db/`: PostgreSQL schema (`schema.sql`).
*   `docs/`: Extensive project documentation.
*   `models/`: Baseline model artifacts.

## Development Commands

*   **Install dependencies**: `pip install -r requirements.txt`
*   **Run Dashboard & API**: `python scripts/run_api.py` (Starts API on `127.0.0.1:8000`)
*   **Run One Cycle**: `python scripts/run_cycle.py`
*   **Run Backtest**: `python scripts/run_backtest.py`
*   **Paper Trading**: `python scripts/run_paper_trading.py`
*   **Init DB**: `python scripts/init_db.py`

## AI Memory

*   Use `docs/ai/` as the shared project memory folder for architecture, commands, testing notes, security notes, task history, decisions, and known issues.
*   After code, command, architecture, configuration, test, or documentation changes, update `docs/ai/TASK_LOG.md` and any other relevant `docs/ai/` files.
*   Run `node scripts/ai-memory/check-memory.mjs` before finishing memory/tooling changes.

## Coding Rules

*   Follow strict type hinting in Python.
*   Preserve the decoupling between pipeline phases (Data -> Indicators -> Models -> Strategy -> Trade -> Risk).
*   Do not hardcode secrets. Use `.env` and `config.py`.

## Architecture Rules

*   **Resilience**: The system must gracefully fallback to in-memory if PostgreSQL is down. If Capital.com API is down, background cycle runner must back off and retry. If a specific ML model artifact is missing, it should fall back to deterministic synthetic inference, not crash the ensemble.
*   **Execution**: Automated execution must remain OFF by default. Do not remove the `CAPITAL_EXECUTION_DEMO_ONLY=1` safety guard rails.

## Security & Safety Rules

*   Never drop or truncate database tables without explicit approval.
*   Never write real passwords or API keys to files.
*   Never run destructive PostgreSQL commands automatically.

## Final Response Format

When answering user requests:
1. Explain what you found.
2. Provide the exact code changes or instructions.
3. List any validation commands the user should run.

## "Do Not Do" Rules

*   Do not rewrite `pipeline.py` or `storage.py` entirely.
*   Do not introduce heavy frontend frameworks (React/Vue/Angular) unless explicitly requested; currently using Vanilla JS.
*   Do not bypass existing risk checks in `risk_engine.py` or `capital_execution.py`.
