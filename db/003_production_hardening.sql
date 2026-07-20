-- Production hardening: provider modes, threshold versioning, audit fields, and validation timelines.

ALTER TABLE trade_recommendations
    ADD COLUMN IF NOT EXISTS strategy_version VARCHAR(80),
    ADD COLUMN IF NOT EXISTS threshold_profile_id BIGINT,
    ADD COLUMN IF NOT EXISTS model_weight_profile_id BIGINT,
    ADD COLUMN IF NOT EXISTS validation_timeline JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE signal_outcomes
    ADD COLUMN IF NOT EXISTS validation_timeline JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS time_to_outcome_seconds INT;

ALTER TABLE economic_news_events
    ADD COLUMN IF NOT EXISTS event_id VARCHAR(160),
    ADD COLUMN IF NOT EXISTS block_before_minutes INT DEFAULT 30,
    ADD COLUMN IF NOT EXISTS block_after_minutes INT DEFAULT 30,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS threshold_profiles (
    id BIGSERIAL PRIMARY KEY,
    version INT NOT NULL,
    name VARCHAR(120) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by VARCHAR(120),
    source_run_id BIGINT,
    config_json JSONB NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS threshold_optimization_runs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120),
    train_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    unseen_test_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    selected_profile_id BIGINT,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS threshold_optimization_results (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT REFERENCES threshold_optimization_runs(id),
    profile_id BIGINT,
    training_score NUMERIC(12, 4),
    validation_score NUMERIC(12, 4),
    unseen_test_score NUMERIC(12, 4),
    selected BOOLEAN DEFAULT FALSE,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_weight_profile_versions (
    id BIGSERIAL PRIMARY KEY,
    version INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    model_weights_json JSONB NOT NULL,
    reason_summary TEXT,
    performance_window INT,
    min_weight NUMERIC(12, 8),
    max_weight NUMERIC(12, 8),
    max_change_per_update NUMERIC(12, 8),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
