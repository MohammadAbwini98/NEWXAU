# 10 - Task Breakdown

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

## Epic 1 - Data Engine

### Task 1.1 - Create candle schema
- Create `market_candles` table.
- Add unique key on instrument, timeframe, candle_time.
- Add indexes for fast query.

### Task 1.2 - Build data importer
- Import historical XAUUSD data.
- Validate timestamp, OHLC, duplicates, and missing candles.

### Task 1.3 - Build timeframe aggregator
- Aggregate 1m to 5m, 15m, and 1h.
- Store generated candles.

### Task 1.4 - Build data quality report
- Missing candles.
- Invalid candles.
- Duplicate candles.
- Data gaps.

---

## Epic 2 - Indicator Engine

### Task 2.1 - Implement trend indicators
- EMA20, EMA50, EMA100, EMA200.
- ADX.
- VWAP.
- Supertrend.

### Task 2.2 - Implement momentum indicators
- RSI.
- MACD.
- Stochastic RSI.
- ROC.
- CCI.

### Task 2.3 - Implement volatility indicators
- ATR.
- Bollinger Bands.
- Keltner Channels.
- Realized volatility.

### Task 2.4 - Implement market structure
- Swing high/low.
- Support/resistance.
- Break of structure.
- Higher high / lower low detection.

### Task 2.5 - Save indicator snapshots
- Store all indicator outputs as JSON.
- Store summarized scores.

---

## Epic 3 - Model Ensemble

### Task 3.1 - Integrate Kronos model runner
- Load fine-tuned model.
- Run prediction on latest window.
- Normalize output.

### Task 3.2 - Build LightGBM/XGBoost model
- Build engineered features.
- Train classifier.
- Save model.
- Add feature importance report.

### Task 3.3 - Build TCN model
- Create 256/512 candle windows.
- Train BUY/SELL/HOLD classifier.
- Save checkpoints.

### Task 3.4 - Build prediction normalizer
- Convert every model output to standard format.

### Task 3.5 - Build weighted ensemble
- Calculate BUY/SELL/HOLD scores.
- Calculate agreement status.
- Store ensemble prediction.

---

## Epic 4 - Strategy Brain

### Task 4.1 - Build ModelConsensusService
- Read latest model predictions.
- Calculate weighted signal direction.

### Task 4.2 - Build IndicatorScoringService
- Score trend, momentum, volatility, and structure.

### Task 4.3 - Build SignalScoringEngine
- Combine model, indicator, structure, entry, and risk scores.

### Task 4.4 - Build SignalBlocker
- Block low-confidence, conflicting, risky, or news-affected signals.

### Task 4.5 - Build ReasonBuilder
- Generate human-readable reasons and blocked reasons.

---

## Epic 5 - Entry / SL / TP Engine

### Task 5.1 - Build EntryPriceEngine
- Market entry.
- Pullback entry.
- Breakout entry.
- Retest entry.

### Task 5.2 - Build StopLossEngine
- ATR-based SL.
- Structure-based SL.
- Combined SL.

### Task 5.3 - Build TakeProfitEngine
- R:R based TP.
- ATR based TP.
- Structure based TP.

### Task 5.4 - Build RiskRewardCalculator
- Validate minimum R:R.
- Return final trade plan.

---

## Epic 6 - Risk Engine

### Task 6.1 - Build spread filter
- Read current spread.
- Compare with max spread.

### Task 6.2 - Build news filter
- Import economic calendar.
- Block high-impact news windows.

### Task 6.3 - Build daily risk limits
- Max daily loss.
- Max consecutive losses.
- Max open recommendations.

### Task 6.4 - Build final risk validation
- Return pass/block result with reasons.

---

## Epic 7 - Dashboard

### Task 7.1 - Build application shell
- Sidebar.
- Top bar.
- Main content area.
- Green/white card layout.

### Task 7.2 - Build dashboard summary cards
- Current Signal.
- Model Consensus.
- Risk Quality.
- Today's Performance.

### Task 7.3 - Build live recommendation panel
- Full signal details.
- Entry, SL, TP.
- Confidence and score.

### Task 7.4 - Build model votes panel
- Model signal.
- Confidence.
- Weight.
- Status.

### Task 7.5 - Build indicator panel
- Trend.
- Momentum.
- Volatility.
- Structure.
- News.

### Task 7.6 - Build chart panel
- Candlestick chart.
- Entry/SL/TP overlays.
- EMA and support/resistance overlays.

### Task 7.7 - Build signal history
- Table.
- Filters.
- Signal details modal.

---

## Epic 8 - Backtesting

### Task 8.1 - Build historical replay engine
- Replay candle by candle.

### Task 8.2 - Run model predictions during replay
- Save simulated predictions.

### Task 8.3 - Simulate trade outcomes
- Entry triggered.
- TP hit.
- SL hit.
- Expired.

### Task 8.4 - Build reports
- Win rate.
- Profit factor.
- Max drawdown.
- R:R.
- Model comparison.

---

## Epic 9 - Paper Trading

### Task 9.1 - Run live 5-minute signal cycle
- Generate signal every 5 minutes.

### Task 9.2 - Track outcomes
- Check whether entry, TP, or SL was reached.

### Task 9.3 - Measure live prediction quality
- BUY precision.
- SELL precision.
- Profit factor.

---

## Epic 10 - Production Safety

### Task 10.1 - Manual confirmation mode
- No automatic execution at first.

### Task 10.2 - Emergency stop
- Disable all signals immediately.

### Task 10.3 - Alerts
- Telegram alerts for recommended and blocked signals.

### Task 10.4 - Monitoring
- Logs.
- Health checks.
- Model status.
- Data freshness.

