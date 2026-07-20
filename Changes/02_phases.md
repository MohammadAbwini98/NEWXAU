# 02 - Implementation Phases

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

## Phase 1 - Data Foundation

### Objective
Prepare clean and reliable Gold/XAUUSD market data.

### Tasks

- Collect historical XAUUSD candles.
- Support multiple timeframes: `1m`, `5m`, `15m`, `1h`.
- Normalize timestamps to UTC.
- Detect missing candles.
- Remove duplicates.
- Validate OHLC consistency:
  - `high >= open`
  - `high >= close`
  - `low <= open`
  - `low <= close`
  - `high >= low`
- Store clean candles in database.
- Create aggregation jobs from `1m` to higher timeframes.

### Deliverables

- Clean candle table
- Data quality report
- Missing candle report
- Aggregation service

---

## Phase 2 - Feature + Indicator Engine

### Objective
Create all technical, statistical, and market structure features needed by models and strategy.

### Tasks

- Calculate trend indicators.
- Calculate momentum indicators.
- Calculate volatility indicators.
- Calculate support/resistance levels.
- Calculate session features.
- Calculate candle pattern features.
- Calculate rolling return features.
- Save feature snapshots per signal cycle.

### Deliverables

- Indicator engine
- Feature table
- Indicator snapshot table
- Indicator scoring service

---

## Phase 3 - Model Ensemble

### Objective
Run multiple models and normalize all outputs into a common signal format.

### Tasks

- Integrate fine-tuned Kronos.
- Train and integrate LightGBM/XGBoost.
- Train and integrate TCN.
- Optionally add CNN+LSTM, PatchTST, N-HiTS, GRU, LSTM, Small Transformer, and 1D CNN.
- Standardize outputs into:
  - `BUY probability`
  - `SELL probability`
  - `HOLD probability`
  - `confidence`
  - `expected_return`
  - `expected_range`
- Store model predictions.

### Deliverables

- Model runners
- Prediction normalizer
- Model prediction table
- Model performance report

---

## Phase 4 - Strategy Brain

### Objective
Convert model predictions and indicator evidence into final trade decisions.

### Tasks

- Build scoring system.
- Build model consensus engine.
- Build trend analyzer.
- Build momentum analyzer.
- Build volatility analyzer.
- Build market structure analyzer.
- Build signal blocker logic.
- Generate final signal status.

### Deliverables

- Strategy Brain service
- Signal scoring engine
- Signal reasons generator
- Blocked reasons generator

---

## Phase 5 - Entry / SL / TP Engine

### Objective
Convert a signal into a tradable plan.

### Tasks

- Determine entry type:
  - Market
  - Pullback
  - Breakout
  - Reversal
- Calculate entry price.
- Calculate stop loss using ATR and structure.
- Calculate TP1, TP2, TP3.
- Validate risk/reward.
- Set signal expiry.

### Deliverables

- Entry engine
- Stop loss engine
- Take profit engine
- Risk/reward calculator

---

## Phase 6 - Risk Engine

### Objective
Prevent unsafe or low-quality signals.

### Tasks

- Validate spread.
- Validate volatility.
- Validate news window.
- Validate max daily loss.
- Validate max consecutive losses.
- Validate position size.
- Validate R:R.
- Validate distance to support/resistance.

### Deliverables

- Risk validation service
- Signal blocker service
- Risk report table

---

## Phase 7 - Web Dashboard

### Objective
Create a professional dashboard showing all signal details in an organized way.

### Tasks

- Build dashboard layout inspired by the attached clean green/white dashboard.
- Add sidebar navigation.
- Add signal summary cards.
- Add live recommendation panel.
- Add model vote panel.
- Add indicator score panel.
- Add Entry/SL/TP card.
- Add risk status card.
- Add signal history table.
- Add backtest analytics.

### Deliverables

- Dashboard UI
- API endpoints
- Real-time updates
- Signal details modal

---

## Phase 8 - Backtesting

### Objective
Validate the system historically before live use.

### Tasks

- Replay candles historically.
- Run models and strategy at each candle.
- Simulate spread, commission, and slippage.
- Calculate win rate, profit factor, max drawdown, and R:R.
- Compare models individually and as ensemble.

### Deliverables

- Backtesting engine
- Backtest report
- Model comparison report
- Trade simulation table

---

## Phase 9 - Paper Trading

### Objective
Validate the system in live market conditions without real money.

### Tasks

- Run every 5 minutes.
- Generate recommendations.
- Track whether TP/SL would be hit.
- Store outcomes.
- Compare predicted direction with actual movement.
- Monitor model drift.

### Deliverables

- Paper trading mode
- Outcome tracker
- Live validation report

---

## Phase 10 - Controlled Live Deployment

### Objective
Move to live execution only after strong paper trading results.

### Tasks

- Enable manual confirmation mode first.
- Limit risk per trade.
- Limit daily trades.
- Enable emergency stop.
- Send Telegram alerts.
- Monitor dashboard continuously.

### Deliverables

- Live mode
- Manual confirmation workflow
- Emergency stop
- Production monitoring

