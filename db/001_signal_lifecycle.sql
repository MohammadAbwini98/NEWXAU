-- Task 01: signal validation, snapshots, and outcome lifecycle fields.

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
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE signal_outcomes
    ADD COLUMN IF NOT EXISTS entry_triggered_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS entry_triggered_price NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS highest_price_after_signal NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS lowest_price_after_signal NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(80),
    ADD COLUMN IF NOT EXISTS pnl_points NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS pnl_percent NUMERIC(12, 6),
    ADD COLUMN IF NOT EXISTS validation_window_candles INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ambiguous_candle BOOLEAN DEFAULT FALSE;
