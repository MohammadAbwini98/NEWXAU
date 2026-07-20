import sys
import os

# Ensure src is in sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import psycopg
from gold_signal_system.config import RuntimeConfig

def clean_db():
    r = RuntimeConfig()
    if not r.postgres_dsn:
        print('No postgres DSN configured.')
        sys.exit(0)
    
    with psycopg.connect(r.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            if r.postgres_schema:
                cur.execute(f'SET search_path TO {r.postgres_schema}, public')
            
            # Tables to truncate to completely wipe XAUUSD history.
            tables_to_truncate = [
                'market_candles', 'indicator_snapshots', 'model_predictions', 
                'ensemble_predictions', 'strategy_decisions', 'trade_recommendations', 
                'model_signal_predictions', 'model_prediction_outcomes', 'signal_snapshots', 
                'signal_entry_plans', 'signal_timeframe_confirmations', 'signal_market_regimes', 
                'risk_checks', 'signal_outcomes', 'backtest_runs', 'backtest_windows', 
                'backtest_signals', 'backtest_trades', 'execution_orders', 
                'execution_account_snapshots', 'walk_forward_runs', 'walk_forward_folds',
                'walk_forward_reports'
            ]
            
            for table in tables_to_truncate:
                try:
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                    print(f'Truncated {table}')
                except Exception as e:
                    print(f'Skipped {table}: {e}')

if __name__ == '__main__':
    clean_db()
