-- Persist important runtime state that must survive API restarts.

ALTER TABLE optimization_runs
    ADD COLUMN IF NOT EXISTS run_id VARCHAR(80),
    ADD COLUMN IF NOT EXISTS config_json JSONB,
    ADD COLUMN IF NOT EXISTS metrics_json JSONB,
    ADD COLUMN IF NOT EXISTS selected_profile_id BIGINT,
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE optimization_runs
SET run_id = COALESCE(run_id, 'OPT-' || id::text),
    config_json = COALESCE(config_json, search_space_json, '{}'::jsonb),
    metrics_json = COALESCE(metrics_json, summary_json, '{}'::jsonb),
    selected_profile_id = COALESCE(selected_profile_id, best_profile_id),
    updated_at = now()
WHERE run_id IS NULL OR config_json IS NULL OR metrics_json IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_optimization_runs_run_id ON optimization_runs(run_id);

ALTER TABLE optimization_candidates
    ADD COLUMN IF NOT EXISTS run_id VARCHAR(80),
    ADD COLUMN IF NOT EXISTS candidate_id INT,
    ADD COLUMN IF NOT EXISTS parameters_json JSONB,
    ADD COLUMN IF NOT EXISTS train_metrics_json JSONB,
    ADD COLUMN IF NOT EXISTS validation_metrics_json JSONB,
    ADD COLUMN IF NOT EXISTS test_metrics_json JSONB,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_optimization_candidates_run_id ON optimization_candidates(run_id);

CREATE TABLE IF NOT EXISTS optimization_profiles (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    instrument VARCHAR(20) DEFAULT 'XAUUSD',
    timeframe VARCHAR(10) DEFAULT '5m',
    is_active BOOLEAN DEFAULT FALSE,
    parameters_json JSONB NOT NULL,
    source_run_id VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS optimization_profile_versions (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL,
    version_number INT NOT NULL,
    parameters_json JSONB NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS optimization_rollbacks (
    id BIGSERIAL PRIMARY KEY,
    from_profile_id BIGINT,
    to_profile_id BIGINT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE system_settings
    ADD COLUMN IF NOT EXISTS setting_value_json JSONB,
    ADD COLUMN IF NOT EXISTS setting_group VARCHAR(80),
    ADD COLUMN IF NOT EXISTS updated_by VARCHAR(120),
    ADD COLUMN IF NOT EXISTS source VARCHAR(80) DEFAULT 'api',
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE system_settings
SET setting_value_json = COALESCE(setting_value_json, setting_value),
    source = COALESCE(source, 'legacy')
WHERE setting_value_json IS NULL;

ALTER TABLE model_weight_profiles
    ADD COLUMN IF NOT EXISTS profile_id VARCHAR(80),
    ADD COLUMN IF NOT EXISTS name VARCHAR(120),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS weights_json JSONB;

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_weight_profiles_profile_id
    ON model_weight_profiles(profile_id)
    WHERE profile_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS model_weight_versions (
    id BIGSERIAL PRIMARY KEY,
    profile_id VARCHAR(80) NOT NULL,
    version_number INT NOT NULL,
    weights_json JSONB NOT NULL,
    reason TEXT,
    metrics_snapshot_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_weight_versions_profile_id ON model_weight_versions(profile_id);

CREATE TABLE IF NOT EXISTS model_weight_adjustments (
    id BIGSERIAL PRIMARY KEY,
    adjustment_id VARCHAR(120) NOT NULL,
    profile_id VARCHAR(80) NOT NULL,
    model_name VARCHAR(80) NOT NULL,
    old_weight NUMERIC(12, 8),
    new_weight NUMERIC(12, 8),
    reason TEXT,
    metrics_window_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_model_weight_adjustments_profile_id ON model_weight_adjustments(profile_id);

CREATE TABLE IF NOT EXISTS health_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(120) NOT NULL UNIQUE,
    severity VARCHAR(20) NOT NULL,
    component VARCHAR(80) NOT NULL,
    message TEXT NOT NULL,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_health_snapshots (
    id BIGSERIAL PRIMARY KEY,
    component VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL,
    latency_ms NUMERIC(12, 4),
    failure_count INT,
    details_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_service_health_snapshots_component ON service_health_snapshots(component, created_at DESC);
