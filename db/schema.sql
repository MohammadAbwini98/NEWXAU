-- XAUUSD Signal System database schema (PostgreSQL)

CREATE TABLE IF NOT EXISTS market_candles (
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

CREATE INDEX IF NOT EXISTS idx_market_candles_lookup
    ON market_candles (instrument, timeframe, candle_time DESC);

CREATE TABLE IF NOT EXISTS indicator_snapshots (
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

CREATE INDEX IF NOT EXISTS idx_indicator_snapshots_lookup
    ON indicator_snapshots (instrument, timeframe, snapshot_time DESC);

CREATE TABLE IF NOT EXISTS model_predictions (
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

CREATE INDEX IF NOT EXISTS idx_model_predictions_lookup
    ON model_predictions (instrument, timeframe, prediction_time DESC, model_name);

CREATE TABLE IF NOT EXISTS ensemble_predictions (
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

CREATE INDEX IF NOT EXISTS idx_ensemble_predictions_lookup
    ON ensemble_predictions (instrument, timeframe, prediction_time DESC);

CREATE TABLE IF NOT EXISTS strategy_decisions (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    decision_time TIMESTAMPTZ NOT NULL,
    signal VARCHAR(10) NOT NULL,
    status VARCHAR(50) NOT NULL,
    score NUMERIC(5, 2),
    confidence NUMERIC(8, 6),
    model_consensus VARCHAR(50),
    indicator_bias VARCHAR(50),
    reasons JSONB,
    blocked_reasons JSONB,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trade_recommendations (
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

CREATE INDEX IF NOT EXISTS idx_trade_recommendations_lookup
    ON trade_recommendations (instrument, timeframe, signal_time DESC);

CREATE TABLE IF NOT EXISTS model_signal_predictions (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trade_recommendations(id),
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(100),
    instrument VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    predicted_signal VARCHAR(10) NOT NULL,
    confidence NUMERIC(8, 6),
    raw_score NUMERIC(12, 6),
    predicted_return NUMERIC(18, 8),
    predicted_high NUMERIC(18, 6),
    predicted_low NUMERIC(18, 6),
    forecast_horizon INT,
    weight_used NUMERIC(12, 8),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_prediction_outcomes (
    id BIGSERIAL PRIMARY KEY,
    model_prediction_id BIGINT REFERENCES model_signal_predictions(id),
    signal_id BIGINT REFERENCES trade_recommendations(id),
    was_direction_correct BOOLEAN,
    was_profitable BOOLEAN,
    actual_outcome VARCHAR(50),
    actual_return NUMERIC(18, 8),
    error_abs NUMERIC(18, 8),
    error_squared NUMERIC(18, 8),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signal_snapshots (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT UNIQUE REFERENCES trade_recommendations(id),
    model_votes_json JSONB NOT NULL,
    model_weights_json JSONB NOT NULL,
    indicator_summary_json JSONB NOT NULL,
    market_structure_json JSONB NOT NULL,
    risk_filters_json JSONB NOT NULL,
    blocked_reasons_json JSONB NOT NULL,
    entry_plan_json JSONB NOT NULL,
    raw_recommendation_json JSONB NOT NULL,
    market_regime_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    multi_timeframe_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    dynamic_weights_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    entry_plans_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signal_entry_plans (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trade_recommendations(id),
    entry_type VARCHAR(50),
    entry_price NUMERIC(18, 6),
    stop_loss NUMERIC(18, 6),
    take_profit_1 NUMERIC(18, 6),
    take_profit_2 NUMERIC(18, 6),
    take_profit_3 NUMERIC(18, 6),
    risk_reward NUMERIC(8, 4),
    plan_score NUMERIC(8, 4),
    selected BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT,
    plan_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signal_timeframe_confirmations (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trade_recommendations(id),
    timeframe VARCHAR(10),
    role VARCHAR(50),
    bias VARCHAR(30),
    score NUMERIC(8, 4),
    reason_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signal_market_regimes (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trade_recommendations(id),
    primary_regime VARCHAR(50),
    regime_confidence NUMERIC(8, 4),
    regime_tags_json JSONB,
    regime_inputs_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_checks (
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

CREATE TABLE IF NOT EXISTS signal_outcomes (
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
    entry_triggered_at TIMESTAMPTZ,
    entry_triggered_price NUMERIC(18, 6),
    highest_price_after_signal NUMERIC(18, 6),
    lowest_price_after_signal NUMERIC(18, 6),
    exit_price NUMERIC(18, 6),
    exit_reason VARCHAR(80),
    pnl_points NUMERIC(18, 6),
    pnl_percent NUMERIC(12, 6),
    validation_window_candles INT DEFAULT 0,
    ambiguous_candle BOOLEAN DEFAULT FALSE,
    raw_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id BIGSERIAL PRIMARY KEY,
    run_name VARCHAR(120),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    settings_json JSONB NOT NULL,
    summary_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_windows (
    id BIGSERIAL PRIMARY KEY,
    backtest_run_id BIGINT REFERENCES backtest_runs(id),
    train_start TIMESTAMPTZ,
    train_end TIMESTAMPTZ,
    test_start TIMESTAMPTZ,
    test_end TIMESTAMPTZ,
    summary_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_signals (
    id BIGSERIAL PRIMARY KEY,
    backtest_run_id BIGINT REFERENCES backtest_runs(id),
    backtest_window_id BIGINT REFERENCES backtest_windows(id),
    signal_snapshot_json JSONB NOT NULL,
    outcome_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT REFERENCES backtest_runs(id),
    trade_time TIMESTAMPTZ NOT NULL,
    signal VARCHAR(10),
    status VARCHAR(50),
    entry_price NUMERIC(18, 6),
    stop_loss NUMERIC(18, 6),
    take_profit_1 NUMERIC(18, 6),
    take_profit_2 NUMERIC(18, 6),
    take_profit_3 NUMERIC(18, 6),
    outcome VARCHAR(50),
    realized_rr NUMERIC(8, 4),
    raw_json JSONB
);

CREATE TABLE IF NOT EXISTS model_performance (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    buy_precision NUMERIC(8, 4),
    sell_precision NUMERIC(8, 4),
    hold_accuracy NUMERIC(8, 4),
    win_rate NUMERIC(8, 4),
    profit_factor NUMERIC(8, 4),
    false_signal_rate NUMERIC(8, 4),
    average_return NUMERIC(18, 8),
    drift_score NUMERIC(8, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_weight_profiles (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    base_weight NUMERIC(12, 8),
    min_weight NUMERIC(12, 8),
    max_weight NUMERIC(12, 8),
    is_enabled BOOLEAN DEFAULT TRUE,
    applies_to_timeframe VARCHAR(10) DEFAULT '*',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_dynamic_weights (
    id BIGSERIAL PRIMARY KEY,
    model_name VARCHAR(50) NOT NULL,
    instrument VARCHAR(20),
    timeframe VARCHAR(10),
    market_regime VARCHAR(50),
    session VARCHAR(50),
    signal_type VARCHAR(10),
    base_weight NUMERIC(12, 8),
    effective_weight NUMERIC(12, 8),
    adjustment_reason_json JSONB,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS economic_news_events (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80),
    event_name VARCHAR(200),
    country VARCHAR(40),
    currency VARCHAR(10),
    impact VARCHAR(20),
    scheduled_at TIMESTAMPTZ,
    actual VARCHAR(80),
    forecast VARCHAR(80),
    previous VARCHAR(80),
    status VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strategy_parameter_profiles (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120),
    instrument VARCHAR(20),
    timeframe VARCHAR(10),
    parameters_json JSONB NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120),
    instrument VARCHAR(20),
    timeframe VARCHAR(10),
    search_space_json JSONB NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(30),
    best_profile_id BIGINT,
    summary_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS optimization_candidates (
    id BIGSERIAL PRIMARY KEY,
    optimization_run_id BIGINT REFERENCES optimization_runs(id),
    profile_id BIGINT,
    metrics_json JSONB NOT NULL,
    score NUMERIC(12, 4),
    rank INT,
    rejected_reason TEXT
);

CREATE TABLE IF NOT EXISTS system_health_events (
    id BIGSERIAL PRIMARY KEY,
    component VARCHAR(80),
    status VARCHAR(20),
    message TEXT,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS system_settings (
    id BIGSERIAL PRIMARY KEY,
    setting_key VARCHAR(120) UNIQUE NOT NULL,
    setting_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
