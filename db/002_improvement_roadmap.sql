-- Tasks 02-11: performance, weights, regimes, entry plans, MTF, news,
-- replay support, walk-forward backtesting, optimization, and health.

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

ALTER TABLE signal_snapshots
    ADD COLUMN IF NOT EXISTS market_regime_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS multi_timeframe_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS dynamic_weights_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS entry_plans_json JSONB NOT NULL DEFAULT '[]'::jsonb;

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
