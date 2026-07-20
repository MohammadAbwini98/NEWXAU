-- Capital.com demo execution audit and account snapshots.

CREATE TABLE IF NOT EXISTS execution_orders (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trade_recommendations(id),
    idempotency_key TEXT UNIQUE NOT NULL,
    instrument TEXT NOT NULL,
    epic TEXT NOT NULL,
    account_id TEXT,
    account_name TEXT,
    environment TEXT NOT NULL DEFAULT 'demo',
    direction TEXT NOT NULL,
    size DOUBLE PRECISION,
    order_type TEXT NOT NULL DEFAULT 'MARKET',
    status TEXT NOT NULL,
    recommendation_status TEXT,
    entry_price DOUBLE PRECISION,
    current_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    take_profit_1 DOUBLE PRECISION,
    take_profit_2 DOUBLE PRECISION,
    take_profit_3 DOUBLE PRECISION,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    deal_reference TEXT,
    deal_id TEXT,
    transaction_id TEXT,
    outcome TEXT NOT NULL DEFAULT 'PENDING',
    outcome_reason TEXT,
    outcome_updated_at TIMESTAMPTZ,
    broker_status TEXT,
    rejection_reason TEXT,
    error_message TEXT,
    request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    confirm_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE execution_orders
    ADD COLUMN IF NOT EXISTS transaction_id TEXT,
    ADD COLUMN IF NOT EXISTS outcome TEXT NOT NULL DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS outcome_reason TEXT,
    ADD COLUMN IF NOT EXISTS outcome_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_execution_orders_signal
    ON execution_orders (signal_id);

CREATE INDEX IF NOT EXISTS idx_execution_orders_status
    ON execution_orders (status, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_orders_outcome
    ON execution_orders (outcome, requested_at DESC);

CREATE INDEX IF NOT EXISTS idx_execution_orders_lookup
    ON execution_orders (instrument, epic, requested_at DESC);

CREATE TABLE IF NOT EXISTS execution_account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    account_id TEXT,
    account_name TEXT,
    environment TEXT NOT NULL DEFAULT 'demo',
    balance DOUBLE PRECISION,
    available DOUBLE PRECISION,
    profit_loss DOUBLE PRECISION,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_execution_account_snapshots_lookup
    ON execution_account_snapshots (account_name, created_at DESC);
