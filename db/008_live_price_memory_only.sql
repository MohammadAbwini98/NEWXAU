-- Live websocket prices are memory-only. Durable records remain in the
-- recommendation, execution, backtest, health, settings, and model tables.
DROP TABLE IF EXISTS latest_market_state;
