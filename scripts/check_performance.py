"""Quick diagnostic with connection timeout."""
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import psycopg
from gold_signal_system.config import RuntimeConfig

def main():
    r = RuntimeConfig()
    dsn = r.postgres_dsn
    if not dsn:
        print("No DSN"); return
    
    # Add connection timeout
    if "?" not in dsn:
        dsn += "?connect_timeout=5"
    else:
        dsn += "&connect_timeout=5"
    
    try:
        conn = psycopg.connect(dsn, autocommit=True)
    except Exception as e:
        print(f"Cannot connect: {e}")
        return
    
    cur = conn.cursor()
    if r.postgres_schema:
        cur.execute(f"SET search_path TO {r.postgres_schema}, public")

    # 1. Total signals
    cur.execute("SELECT COUNT(*) FROM trade_recommendations")
    total = cur.fetchone()[0]
    print(f"=== TOTAL SIGNALS: {total} ===")

    # 2. Signal breakdown
    cur.execute("SELECT signal, status, COUNT(*) FROM trade_recommendations GROUP BY signal, status ORDER BY COUNT(*) DESC")
    print("\nSignal/Status breakdown:")
    for row in cur.fetchall():
        print(f"  {row[0]:6s} | {str(row[1]):40s} | count={row[2]}")

    # 3. Confidence
    cur.execute("SELECT signal, ROUND(AVG(confidence)::numeric,4), ROUND(MIN(confidence)::numeric,4), ROUND(MAX(confidence)::numeric,4), COUNT(*) FROM trade_recommendations GROUP BY signal")
    print("\nConfidence:")
    for row in cur.fetchall():
        print(f"  {row[0]:6s} | avg={row[1]} min={row[2]} max={row[3]} count={row[4]}")

    # 4. Last 10 signals
    cur.execute("SELECT signal_time, signal, status, confidence, score, entry_price, stop_loss, take_profit_1 FROM trade_recommendations ORDER BY signal_time DESC LIMIT 10")
    print("\nLast 10 signals:")
    for row in cur.fetchall():
        print(f"  {row[0]} | {row[1]:5s} | {str(row[2]):40s} | conf={row[3]} score={row[4]} | entry={row[5]} sl={row[6]} tp1={row[7]}")

    # 5. Execution orders
    cur.execute("SELECT COUNT(*) FROM execution_orders")
    ec = cur.fetchone()[0]
    print(f"\n=== EXECUTION ORDERS: {ec} ===")
    if ec > 0:
        cur.execute("SELECT created_at, instrument, direction, status, outcome, size, entry_price, exit_price, pnl FROM execution_orders ORDER BY created_at DESC LIMIT 15")
        for row in cur.fetchall():
            print(f"  {row[0]} | {row[1]} {row[2]:5s} | {row[3]} | {row[4]} | sz={row[5]} entry={row[6]} exit={row[7]} pnl={row[8]}")

    # 6. Model predictions
    cur.execute("SELECT model_name, signal, ROUND(AVG(confidence)::numeric,4), COUNT(*) FROM model_predictions GROUP BY model_name, signal ORDER BY model_name, signal")
    print("\nModel predictions:")
    for row in cur.fetchall():
        print(f"  {row[0]:15s} | {row[1]:5s} | avg_conf={row[2]} count={row[3]}")

    # 7. Ensemble
    cur.execute("SELECT ensemble_signal, ROUND(AVG(ensemble_confidence)::numeric,4), ROUND(AVG(buy_score)::numeric,4), ROUND(AVG(sell_score)::numeric,4), ROUND(AVG(hold_score)::numeric,4), COUNT(*) FROM ensemble_predictions GROUP BY ensemble_signal")
    print("\nEnsemble:")
    for row in cur.fetchall():
        print(f"  {row[0]:5s} | conf={row[1]} | buy={row[2]} sell={row[3]} hold={row[4]} | count={row[5]}")

    # 8. Risk checks
    try:
        cur.execute("SELECT risk_status, COUNT(*), ROUND(AVG(risk_reward)::numeric,2) FROM risk_checks GROUP BY risk_status")
        print("\nRisk checks:")
        for row in cur.fetchall():
            print(f"  {row[0]:10s} | count={row[1]} | avg_rr={row[2]}")
    except:
        pass

    # 9. Market candles
    cur.execute("SELECT timeframe, COUNT(*), MIN(candle_time), MAX(candle_time) FROM market_candles WHERE instrument=%s GROUP BY timeframe ORDER BY timeframe", (r.instrument,))
    print(f"\nMarket candles ({r.instrument}):")
    for row in cur.fetchall():
        print(f"  {row[0]:5s} | {row[1]:6d} candles | {row[2]} to {row[3]}")

    conn.close()

if __name__ == "__main__":
    main()
