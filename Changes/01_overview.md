# 01 - Gold Signal System Overview

## Document Map

- [01 - Overview](01_overview.md)
- [02 - Phases](02_phases.md)
- [03 - Models](03_models.md)
- [04 - Indicators](04_indicators.md)
- [05 - Strategy](05_strategy.md)
- [06 - Entry / SL / TP](06_entry.md)
- [07 - Risk](07_risk.md)
- [08 - Dashboard](08_dashboard.md)
- [09 - Database](09_database.md)
- [10 - Tasks](10_tasks.md)

## Goal

Build a professional Gold/XAUUSD signal recommendation system that combines:

- Fine-tuned Kronos model
- Smaller from-scratch models
- Massive indicator engine
- Strategy Brain
- Entry / SL / TP engine
- Risk engine
- Web dashboard inspired by the attached clean green-and-white task dashboard design

The final output must not be only `BUY`, `SELL`, or `HOLD`. It must be a full recommendation object with confidence, entry price, stop loss, take profits, risk/reward, reasons, blocked reasons, model votes, indicator summary, and expiry.

---

## Core Principle

```text
Models predict.
Indicators confirm.
Strategy Brain decides.
Risk Engine protects.
Entry / SL / TP Engine makes the signal tradable.
Dashboard explains everything clearly.
```

---

## High-Level Architecture

```text
XAUUSD Market Data
        ↓
Data Quality + Candle Builder
        ↓
Feature + Indicator Engine
        ↓
Model Ensemble
        ↓
Prediction Normalizer
        ↓
Strategy Brain
        ↓
Entry / SL / TP Engine
        ↓
Risk Engine
        ↓
Final Recommendation Builder
        ↓
Database + Dashboard + Telegram
```

---

## Main Components

| Component | Responsibility |
|---|---|
| Data Engine | Collect, clean, validate, and aggregate XAUUSD candles |
| Feature Engine | Build returns, rolling values, sessions, volatility, structure features |
| Indicator Engine | Calculate trend, momentum, volatility, support/resistance, market structure indicators |
| Model Ensemble | Run Kronos, TCN, LightGBM, PatchTST, CNN+LSTM, N-HiTS, etc. |
| Strategy Brain | Convert model predictions + indicator evidence into signal decisions |
| Entry Engine | Select market, pullback, breakout, or reversal entry |
| SL Engine | Calculate dynamic stop loss using ATR and market structure |
| TP Engine | Calculate TP1, TP2, TP3 using R:R, ATR, forecast range, and support/resistance |
| Risk Engine | Block unsafe trades based on spread, R:R, drawdown, news, volatility, and limits |
| Dashboard | Show complete explanation, signal quality, model votes, indicators, and trade plan |

---

## Final Signal Types

```text
RECOMMENDED
WEAK_RECOMMENDATION
HOLD
BLOCKED_BY_LOW_CONFIDENCE
BLOCKED_BY_MODEL_CONFLICT
BLOCKED_BY_RISK
BLOCKED_BY_SPREAD
BLOCKED_BY_NEWS
BLOCKED_BY_LOW_RR
BLOCKED_BY_BAD_ENTRY
BLOCKED_BY_MARKET_STRUCTURE
```

---

## Final Recommendation Example

```json
{
  "instrument": "XAUUSD",
  "timeframe": "5m",
  "signal": "BUY",
  "status": "RECOMMENDED",
  "confidence": 0.78,
  "score": 85,
  "entry_type": "LIMIT_PULLBACK",
  "entry_price": 2351.80,
  "current_price": 2354.20,
  "stop_loss": 2348.60,
  "take_profit_1": 2355.00,
  "take_profit_2": 2358.20,
  "take_profit_3": 2364.50,
  "risk_reward": 2.0,
  "valid_for_minutes": 15,
  "model_consensus": "BULLISH",
  "indicator_bias": "BULLISH",
  "risk_status": "PASSED",
  "reasons": [
    "Kronos, TCN and LightGBM agree on BUY direction.",
    "Price remains above EMA50 and EMA200.",
    "Pullback entry gives better risk/reward than market entry.",
    "ATR supports enough movement for target distance."
  ],
  "blocked_reasons": []
}
```

---

## Recommended Build Order

1. Data foundation
2. Indicator engine
3. Model ensemble
4. Strategy Brain
5. Entry / SL / TP engine
6. Risk engine
7. Dashboard
8. Backtesting
9. Paper trading
10. Live controlled deployment

