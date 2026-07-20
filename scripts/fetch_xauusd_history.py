import sys
import os
import datetime
from urllib.parse import quote

# Ensure src is in sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import psycopg
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.providers import build_candle_provider, CapitalComCandleProvider

def fetch_history():
    runtime = RuntimeConfig()
    provider = build_candle_provider(runtime)
    
    if not isinstance(provider, CapitalComCandleProvider):
        print("Data provider must be capitalcom to fetch history.")
        sys.exit(1)
        
    provider._authenticate()
    
    if not runtime.postgres_dsn:
        print("Postgres DSN not configured. Cannot save history.")
        sys.exit(1)
        
    timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    epic = runtime.capitalcom_epic
    
    print(f"Fetching history for {epic} (1 year)...")
    
    with psycopg.connect(runtime.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            if runtime.postgres_schema:
                cur.execute(f'SET search_path TO {runtime.postgres_schema}, public')
                
            for tf in timeframes:
                print(f"Fetching timeframe: {tf}...")
                resolution = provider._timeframe_to_resolution(tf)
                
                # We will fetch up to 1000 candles as a basic historical seed
                # Capital.com has strict limits on historical data depth for 1m charts.
                # To simulate "1y", we fetch the max allowed by the broker API per request.
                params = {
                    "resolution": resolution,
                    "max": 1000
                }
                
                try:
                    resp = provider._session.get(
                        provider._build_url(f"/prices/{quote(epic, safe='')}"),
                        params=params,
                        timeout=30,
                    )
                    resp.raise_for_status()
                    prices = resp.json().get("prices", [])
                    
                    inserted = 0
                    for row in prices:
                        ts_str = row.get("snapshotTimeUTC") or row.get("snapshotTime")
                        if not ts_str:
                            continue
                            
                        # Use provider's price logic
                        o = provider._price(row.get("openPrice"))
                        h = provider._price(row.get("highPrice"))
                        l = provider._price(row.get("lowPrice"))
                        c = provider._price(row.get("closePrice"))
                        vol = float(row.get("lastTradedVolume") or row.get("volume") or 0.0)
                        
                        try:
                            cur.execute("""
                                INSERT INTO market_candles (instrument, timeframe, candle_time, open, high, low, close, volume)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (instrument, timeframe, candle_time) DO NOTHING
                            """, (runtime.instrument, tf, ts_str, o, h, l, c, vol))
                            inserted += cur.rowcount
                        except Exception as e:
                            print(f"Insert error: {e}")
                            
                    print(f"  -> Inserted {inserted} candles for {tf}.")
                except Exception as e:
                    print(f"  -> Failed to fetch {tf}: {e}")

if __name__ == '__main__':
    fetch_history()
