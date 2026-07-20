-- Durable backtest and walk-forward execution history.
-- This migration upgrades the older backtest tables in-place.

ALTER TABLE backtest_runs
    ADD COLUMN IF NOT EXISTS run_id VARCHAR(80),
    ADD COLUMN IF NOT EXISTS run_type VARCHAR(30) DEFAULT 'BACKTEST',
    ADD COLUMN IF NOT EXISTS instrument VARCHAR(20) DEFAULT 'XAUUSD',
    ADD COLUMN IF NOT EXISTS timeframe VARCHAR(10) DEFAULT '1m',
    ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'CREATED',
    ADD COLUMN IF NOT EXISTS config_json JSONB,
    ADD COLUMN IF NOT EXISTS report_path TEXT,
    ADD COLUMN IF NOT EXISTS error_message TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE backtest_runs
SET run_id = COALESCE(run_id, 'LEGACY-' || id::text),
    run_type = COALESCE(run_type, 'BACKTEST'),
    instrument = COALESCE(instrument, 'XAUUSD'),
    timeframe = COALESCE(timeframe, '1m'),
    status = COALESCE(status, CASE WHEN completed_at IS NULL THEN 'COMPLETED' ELSE 'COMPLETED' END),
    config_json = COALESCE(config_json, settings_json, '{}'::jsonb),
    updated_at = now()
WHERE run_id IS NULL OR config_json IS NULL;

ALTER TABLE backtest_runs
    ALTER COLUMN run_id SET NOT NULL,
    ALTER COLUMN summary_json DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_backtest_runs_run_id ON backtest_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_completed_at ON backtest_runs(completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_status ON backtest_runs(status);

ALTER TABLE backtest_trades DROP CONSTRAINT IF EXISTS backtest_trades_run_id_fkey;
ALTER TABLE backtest_trades
    ALTER COLUMN run_id TYPE VARCHAR(80) USING run_id::text,
    ALTER COLUMN trade_time DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS signal_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS signal_direction VARCHAR(10),
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS pnl NUMERIC(18, 6),
    ADD COLUMN IF NOT EXISTS risk_reward NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(8, 4),
    ADD COLUMN IF NOT EXISTS score NUMERIC(12, 4),
    ADD COLUMN IF NOT EXISTS entry_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS exit_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reason_json JSONB,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

UPDATE backtest_trades
SET signal_time = COALESCE(signal_time, trade_time),
    signal_direction = COALESCE(signal_direction, signal),
    risk_reward = COALESCE(risk_reward, realized_rr),
    pnl = COALESCE(pnl, realized_rr),
    reason_json = COALESCE(reason_json, raw_json, '{}'::jsonb)
WHERE signal_time IS NULL OR signal_direction IS NULL OR reason_json IS NULL;

CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_id ON backtest_trades(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_signal_time ON backtest_trades(signal_time DESC);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(80) NOT NULL,
    metric_name VARCHAR(120) NOT NULL,
    metric_value NUMERIC(18, 8),
    metrics_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_backtest_metrics_run_id ON backtest_metrics(run_id);

CREATE TABLE IF NOT EXISTS walk_forward_runs (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(80) NOT NULL UNIQUE,
    backtest_run_id VARCHAR(80),
    instrument VARCHAR(20) DEFAULT 'XAUUSD',
    timeframe VARCHAR(10) DEFAULT '1m',
    status VARCHAR(30) DEFAULT 'CREATED',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    config_json JSONB,
    summary_json JSONB,
    report_path TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS walk_forward_folds (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(80) NOT NULL,
    fold_number INT NOT NULL,
    train_start TIMESTAMPTZ,
    train_end TIMESTAMPTZ,
    test_start TIMESTAMPTZ,
    test_end TIMESTAMPTZ,
    status VARCHAR(30) DEFAULT 'COMPLETED',
    metrics_json JSONB,
    report_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_walk_forward_folds_run_id ON walk_forward_folds(run_id);

CREATE TABLE IF NOT EXISTS walk_forward_reports (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(80) NOT NULL,
    report_type VARCHAR(50) NOT NULL,
    report_path TEXT NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_walk_forward_reports_run_id ON walk_forward_reports(run_id);
