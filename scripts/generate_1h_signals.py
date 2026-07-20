r"""Generate signals natively on 1h data and print them, to verify the 1h stack works.

Uses an in-memory storage (postgres_dsn=None) so it does NOT touch the live DB, and
feeds real 1h candles with source_timeframe="1h" so the pipeline runs on 1h (not the
1m live-fallback). Prints the decision for the last N 1h closes, with trade plan.

    .\.venv\Scripts\python.exe scripts\generate_1h_signals.py --count 15
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gold_signal_system.config import RuntimeConfig  # noqa: E402
from gold_signal_system.contracts import MarketContext, SignalDirection  # noqa: E402
from gold_signal_system.pipeline import GoldSignalSystem  # noqa: E402


def load_1h_candle_dicts(runtime: RuntimeConfig, limit: int) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    schema = runtime.postgres_schema or "public"
    sql = (
        f'SELECT candle_time, open, high, low, close, volume FROM "{schema}".market_candles '
        f"WHERE instrument=%s AND timeframe='1h' ORDER BY candle_time DESC LIMIT %s"
    )
    with psycopg.connect(runtime.postgres_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (runtime.instrument, limit))
            rows = list(cur.fetchall())
    rows.reverse()
    return [
        {
            "candle_time": r["candle_time"].isoformat(),
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "volume": float(r["volume"] or 0.0),
        }
        for r in rows
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=15, help="how many recent 1h closes to evaluate")
    ap.add_argument("--window", type=int, default=320, help="1h candles fed per evaluation")
    args = ap.parse_args()

    live_runtime = RuntimeConfig()  # reads real DSN for read-only candle pull
    print(f"cycle_timeframe={live_runtime.cycle_timeframe}  horizon={live_runtime.prediction_horizon_candles}  "
          f"gate={live_runtime.minimum_final_confidence}  REC>={live_runtime.recommended_score} "
          f"WEAK>={live_runtime.weak_recommendation_score}", flush=True)

    candles = load_1h_candle_dicts(live_runtime, args.window + args.count + 5)
    print(f"loaded {len(candles)} real 1h candles ({candles[0]['candle_time']} .. {candles[-1]['candle_time']})\n", flush=True)

    # In-memory storage so we never write to the live DB.
    runtime = RuntimeConfig(postgres_dsn=None)
    system = GoldSignalSystem(runtime=runtime)

    # Historical replay: evaluate the candle-freshness health gate as of each bar's
    # own close time (not wall-clock now), otherwise every replayed bar looks "stale".
    import types
    from datetime import timedelta

    def _readiness(self, cdls, tf="5m"):
        sim_now = cdls[-1].candle_time + timedelta(minutes=5)
        h = self.check(cdls, tf, now=sim_now)
        h["trading_allowed"] = h["overall_status"] != "CRITICAL"
        return h

    system.health_service.check_trading_readiness = types.MethodType(_readiness, system.health_service)

    tally: Counter = Counter()
    n = len(candles)
    start = max(args.window, n - args.count)
    print(f"{'time (UTC)':20} {'signal':6} {'status':24} {'conf':>5} {'score':>5}  trade plan", flush=True)
    print("-" * 100, flush=True)
    for k in range(start, n + 1):
        window = candles[max(0, k - args.window): k]
        if len(window) < 40:
            continue
        result = system.run_signal_cycle(raw_candles=window, source_timeframe="1h", market_context=MarketContext())
        rec = result.recommendation
        tally[rec.status.value] += 1
        ts = window[-1]["candle_time"][:16].replace("T", " ")
        plan = ""
        if rec.signal != SignalDirection.HOLD and rec.entry_price is not None:
            plan = (f"entry={rec.entry_price:.1f} SL={rec.stop_loss:.1f} "
                    f"TP1={rec.take_profit_1:.1f} TP3={rec.take_profit_3:.1f} RR={rec.risk_reward}")
        print(f"{ts:20} {rec.signal.value:6} {rec.status.value:24} {rec.confidence:5.2f} {rec.score:5.1f}  {plan}",
              flush=True)

    print("\nstatus tally:", dict(tally), flush=True)

    # Show the model votes behind the most recent decision.
    print("\nlatest-bar model votes:", flush=True)
    for v in result.recommendation.model_votes:
        print(f"  {v.model_name:10} {v.signal.value:5} buy={v.buy_probability:.2f} "
              f"sell={v.sell_probability:.2f} hold={v.hold_probability:.2f} conf={v.confidence:.2f}", flush=True)


if __name__ == "__main__":
    main()
