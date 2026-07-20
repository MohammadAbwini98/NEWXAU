# Project Context

## Overview
*   **Project Name**: NEWXAU / XAUUSD Signal Recommendation System.
*   **Purpose**: A full end-to-end signal engine and trading dashboard capable of reading live candles, calculating indicators, running ensemble ML inference, deciding on entries/SL/TP, and optionally pushing trades to Capital.com.
*   **Main Business/Domain Goal**: Provide algorithmic trading recommendations (Signals) using a combination of technical indicators, multi-timeframe analysis, and Machine Learning models.

## Main Modules
*   **Data Engine**: Fetches candles (Capital.com, CSV, Mock).
*   **Indicator Engine**: Computes RSI, MACD, ATR, EMA, Bollinger Bands, SMC blocks, etc.
*   **Model Ensemble**: Runs TCN, LightGBM, PatchTST, CNN-LSTM, NHITS, Kronos.
*   **Strategy Brain**: Aggregates models & indicators to generate consensus bias.
*   **Trade Plan Engine**: Calculates Entry, Stop Loss, and Take Profit levels.
*   **Risk Engine**: Validates capital sizing and margin constraints.
*   **Capital Execution**: Pushes demo trades directly to Capital.com via their API.
*   **Dashboard / API**: FastAPI REST endpoints + Websockets + Static HTML/JS frontend.

## External Integrations
*   **Capital.com API**: Used for both live candle fetching and live (demo) order execution.
*   **HuggingFace Hub**: For downloading pretrained `Kronos` weights if available.

## Runtime Behavior & Workflows
*   The system can run one-off cycles, backtests, or paper-trade simulations.
*   In "Background Runner" mode (`ENABLE_BACKGROUND_CYCLE_RUNNER=1`), the system wakes up on a schedule (e.g., every 5 min) to fetch data, run the pipeline, update models, and push updates via websockets to connected clients.
*   The system automatically degrades gracefully: if PostgreSQL is missing, it uses memory. If models are missing, it uses synthetic determinism.

## Known Constraints
*   Execution is specifically gated behind demo-only checks to prevent accidental real-money trading.
*   The system leverages existing Kronos project `.env` parameters if they exist, to seamlessly merge or share config settings.

## Unknowns Found During Review
*   Playwright / Browser automation: Not found in codebase. No E2E browser tests discovered.
*   Real money trading logic: Disabled/Gated via `CAPITAL_EXECUTION_DEMO_ONLY`.
