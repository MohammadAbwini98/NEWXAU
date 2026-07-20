-- Operator-controlled Capital.com execution gates and audit decisions.

CREATE TABLE IF NOT EXISTS execution_control_decisions (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trade_recommendations(id),
    source TEXT NOT NULL DEFAULT 'manual',
    source_kind TEXT NOT NULL DEFAULT 'manual',
    applied BOOLEAN NOT NULL DEFAULT TRUE,
    allowed BOOLEAN NOT NULL,
    reason TEXT NOT NULL,
    session_name TEXT NOT NULL DEFAULT 'UNKNOWN',
    ensemble_signal TEXT,
    kronos_signal TEXT,
    kronos_relation TEXT NOT NULL DEFAULT 'UNKNOWN',
    directional_vote_tie BOOLEAN NOT NULL DEFAULT FALSE,
    buy_votes INT NOT NULL DEFAULT 0,
    sell_votes INT NOT NULL DEFAULT 0,
    hold_votes INT NOT NULL DEFAULT 0,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_execution_control_decisions_created
    ON execution_control_decisions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_control_decisions_signal
    ON execution_control_decisions (signal_id);

CREATE INDEX IF NOT EXISTS idx_execution_control_decisions_allowed_session
    ON execution_control_decisions (allowed, session_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_control_decisions_relation
    ON execution_control_decisions (kronos_relation, created_at DESC);
