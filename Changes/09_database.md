# 09 - Database Design

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

Store all market data, features, model predictions, strategy decisions, risk checks, and outcomes.

Recommended database: PostgreSQL.

---

## Tables

```text
market_candles
indicator_snapshots
model_predictions
ensemble_predictions
strategy_decisions
trade_recommendations
risk_checks
signal_outcomes
backtest_runs
backtest_trades
model_performance
system_settings
```

---

## market_candles

Stores OHLCV candles.

```sql
CREATE TABLE market_candles (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    candle_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(18, 6) NOT NULL,
    high NUMERIC(18, 6) NOT NULL,
    low NUMERIC(18, 6) NOT NULL,
    close NUMERIC(18, 6) NOT NULL,
    volume NUMERIC(18, 6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (instrument, timeframe, candle_time)
);
```

---

## indicator_snapshots

Stores indicators for each signal cycle.

```sql
CREATE TABLE indicator_snapshots (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    snapshot_time TIMESTAMPTZ NOT NULL,
    trend_bias VARCHAR(20),
    trend_score NUMERIC(5, 2),
    momentum_bias VARCHAR(20),
    momentum_score NUMERIC(5, 2),
    volatility_status VARCHAR(20),
    atr NUMERIC(18, 6),
    nearest_support NUMERIC(18, 6),
    nearest_resistance NUMERIC(18, 6),
    structure_bias VARCHAR(50),
    session_name VARCHAR(30),
    news_status VARCHAR(30),
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## model_predictions

Stores each individual model output.

```sql
CREATE TABLE model_predictions (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    prediction_time TIMESTAMPTZ NOT NULL,
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(100),
    signal VARCHAR(10) NOT NULL,
    buy_probability NUMERIC(8, 6),
    sell_probability NUMERIC(8, 6),
    hold_probability NUMERIC(8, 6),
    confidence NUMERIC(8, 6),
    expected_return NUMERIC(18, 8),
    expected_range NUMERIC(18, 6),
    horizon_candles INT,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## ensemble_predictions

Stores combined model result.

```sql
CREATE TABLE ensemble_predictions (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    prediction_time TIMESTAMPTZ NOT NULL,
    ensemble_signal VARCHAR(10) NOT NULL,
    ensemble_confidence NUMERIC(8, 6),
    buy_score NUMERIC(8, 6),
    sell_score NUMERIC(8, 6),
    hold_score NUMERIC(8, 6),
    agreement_status VARCHAR(30),
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## trade_recommendations

Stores final recommendations.

```sql
CREATE TABLE trade_recommendations (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    signal VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL,
    confidence NUMERIC(8, 6),
    score NUMERIC(5, 2),
    entry_type VARCHAR(50),
    entry_price NUMERIC(18, 6),
    current_price NUMERIC(18, 6),
    stop_loss NUMERIC(18, 6),
    take_profit_1 NUMERIC(18, 6),
    take_profit_2 NUMERIC(18, 6),
    take_profit_3 NUMERIC(18, 6),
    risk_reward NUMERIC(8, 4),
    valid_until TIMESTAMPTZ,
    model_consensus VARCHAR(50),
    indicator_bias VARCHAR(50),
    risk_status VARCHAR(50),
    reasons JSONB,
    blocked_reasons JSONB,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## risk_checks

Stores risk validation details.

```sql
CREATE TABLE risk_checks (
    id BIGSERIAL PRIMARY KEY,
    recommendation_id BIGINT REFERENCES trade_recommendations(id),
    risk_status VARCHAR(50) NOT NULL,
    spread NUMERIC(18, 6),
    max_allowed_spread NUMERIC(18, 6),
    risk_reward NUMERIC(8, 4),
    news_status VARCHAR(50),
    volatility_status VARCHAR(50),
    daily_loss_percent NUMERIC(8, 4),
    consecutive_losses INT,
    blocked_reasons JSONB,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## signal_outcomes

Tracks what happened after the recommendation.

```sql
CREATE TABLE signal_outcomes (
    id BIGSERIAL PRIMARY KEY,
    recommendation_id BIGINT REFERENCES trade_recommendations(id),
    outcome VARCHAR(50),
    entry_triggered BOOLEAN DEFAULT FALSE,
    hit_tp1 BOOLEAN DEFAULT FALSE,
    hit_tp2 BOOLEAN DEFAULT FALSE,
    hit_tp3 BOOLEAN DEFAULT FALSE,
    hit_sl BOOLEAN DEFAULT FALSE,
    max_favorable_move NUMERIC(18, 6),
    max_adverse_move NUMERIC(18, 6),
    realized_rr NUMERIC(8, 4),
    closed_at TIMESTAMPTZ,
    raw_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

