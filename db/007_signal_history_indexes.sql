-- Indexes supporting the dashboard Signal History table (filtering + pagination).
-- All queries order by signal_time DESC and page with LIMIT/OFFSET, so each filter
-- column is paired with signal_time DESC to keep the ordered scan cheap.

-- Default (unfiltered) ordering + pagination.
CREATE INDEX IF NOT EXISTS idx_trade_recommendations_signal_time
    ON trade_recommendations (signal_time DESC);

-- Filter by status (e.g. RECOMMENDED, BLOCKED_BY_RISK).
CREATE INDEX IF NOT EXISTS idx_trade_recommendations_status
    ON trade_recommendations (status, signal_time DESC);

-- Filter by direction (BUY / SELL / HOLD).
CREATE INDEX IF NOT EXISTS idx_trade_recommendations_signal
    ON trade_recommendations (signal, signal_time DESC);

-- Filter by validated outcome (raw_json->>'outcome_status': WIN, LOSS, EXPIRED, ...).
CREATE INDEX IF NOT EXISTS idx_trade_recommendations_outcome
    ON trade_recommendations ((raw_json->>'outcome_status'), signal_time DESC);
