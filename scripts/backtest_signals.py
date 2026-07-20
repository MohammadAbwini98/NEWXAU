r"""Measure whether the system's actionable signals have a real, profitable edge.

Runs the true decision path (models -> ensemble -> StrategyBrain) over historical
1h windows and, for each RECOMMENDED/WEAK BUY/SELL signal, measures the realized
forward outcome over the prediction horizon. Reports hit-rate and expectancy by
decision tier and by directional-confidence bucket, plus a simple ATR SL/TP sim.

Sampling is strided to be >= horizon so forward windows don't overlap (independent
samples => trustworthy edge estimate). Run as a background job (loads Kronos).

    .\.venv\Scripts\python.exe scripts\backtest_signals.py --samples 1500 --cost-bps 4
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gold_signal_system.config import ModelWeights, RuntimeConfig  # noqa: E402
from gold_signal_system.contracts import RecommendationStatus, SignalDirection  # noqa: E402
from gold_signal_system.indicator_engine import FeatureIndicatorEngine  # noqa: E402
from gold_signal_system.model_ensemble import ModelEnsembleEngine  # noqa: E402
from gold_signal_system.strategy_brain import StrategyBrain, StrategyThresholdProfile  # noqa: E402
from training.dataset import load_candles, INFERENCE_WINDOW  # noqa: E402

ACTIONABLE = {RecommendationStatus.RECOMMENDED, RecommendationStatus.WEAK_RECOMMENDATION}


def _summary(rows: list[dict], cost: float) -> str:
    if not rows:
        return "no trades"
    rr = np.array([r["dir_return"] for r in rows]) - cost
    hit = float((rr > 0).mean())
    exp = float(rr.mean())
    gross_win = rr[rr > 0].sum()
    gross_loss = -rr[rr < 0].sum()
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    atr_rr = np.array([r["atr_rr"] for r in rows])
    return (f"n={len(rows):4d}  hit={hit:5.1%}  expectancy={exp*100:+.3f}%/trade  "
            f"profit_factor={pf:4.2f}  mean_ATR_RR={atr_rr.mean():+.2f}")


def main() -> None:
    runtime = RuntimeConfig()
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframe", default=runtime.cycle_timeframe)
    ap.add_argument("--samples", type=int, default=1500)
    ap.add_argument("--cost-bps", type=float, default=4.0, help="round-trip cost in basis points")
    ap.add_argument("--atr-sl", type=float, default=1.5, help="stop = entry -/+ atr_sl*ATR")
    ap.add_argument("--atr-tp", type=float, default=2.5, help="target = entry +/- atr_tp*ATR")
    ap.add_argument("--start-frac", type=float, default=0.0,
                    help="only backtest candles after this fraction of history (0.8 = out-of-sample tail, models trained on first 80%)")
    args = ap.parse_args()

    horizon = runtime.prediction_horizon_candles
    cost = args.cost_bps / 10_000.0
    engine = FeatureIndicatorEngine()
    ens_engine = ModelEnsembleEngine(runtime=runtime, model_weights=ModelWeights())
    profile = StrategyThresholdProfile(
        minimum_final_confidence=runtime.minimum_final_confidence,
        recommended_score=runtime.recommended_score,
        weak_recommendation_score=runtime.weak_recommendation_score,
    )
    brain = StrategyBrain(profile)

    candles = load_candles(runtime, args.timeframe)
    closes = np.array([c.close for c in candles])
    eligible = list(range(INFERENCE_WINDOW - 1, len(candles) - horizon))
    if args.start_frac > 0:
        cut = int(len(candles) * args.start_frac)
        eligible = [i for i in eligible if i >= cut]
        print(f"OUT-OF-SAMPLE: restricting to candles after index {cut} "
              f"(last {(1 - args.start_frac) * 100:.0f}% — models trained on earlier data)", flush=True)
    stride = max(horizon, len(eligible) // args.samples)
    sample_idx = eligible[::stride]
    print(f"{args.timeframe} backtest | horizon={horizon} | {len(sample_idx)} non-overlapping samples "
          f"(stride={stride}) | cost={args.cost_bps}bps", flush=True)

    by_tier: dict[str, list[dict]] = defaultdict(list)
    by_conf: dict[str, list[dict]] = defaultdict(list)
    all_dir: list[dict] = []   # every BUY/SELL ensemble signal regardless of status (edge baseline)

    for n, i in enumerate(sample_idx):
        window = candles[i - (INFERENCE_WINDOW - 1): i + 1]
        features = engine.compute_features(window)
        snapshot = engine.build_indicator_snapshot(runtime.instrument, args.timeframe, window)
        votes = ens_engine.run_models(snapshot, features, prediction_time=datetime.now(tz=UTC), candles=window)
        ensemble = ens_engine.build_ensemble(votes)
        decision = brain.evaluate(ensemble, snapshot)

        sig = decision.signal
        if sig not in (SignalDirection.BUY, SignalDirection.SELL):
            continue

        entry = closes[i]
        fwd = closes[i + horizon] / entry - 1.0
        dir_return = fwd if sig == SignalDirection.BUY else -fwd

        # ATR-based SL/TP simulation over the horizon (RR units).
        atr = max(snapshot.atr, 1e-9)
        sl_dist = args.atr_sl * atr
        tp_dist = args.atr_tp * atr
        path = closes[i + 1: i + horizon + 1]
        atr_rr = 0.0
        for px in path:
            move = (px - entry) if sig == SignalDirection.BUY else (entry - px)
            if move <= -sl_dist:
                atr_rr = -1.0
                break
            if move >= tp_dist:
                atr_rr = args.atr_tp / args.atr_sl
                break
        else:
            atr_rr = (path[-1] - entry if sig == SignalDirection.BUY else entry - path[-1]) / sl_dist

        directional_total = ensemble.buy_score + ensemble.sell_score
        win = ensemble.buy_score if sig == SignalDirection.BUY else ensemble.sell_score
        dconf = win / directional_total if directional_total > 0 else 0.0

        row = {"dir_return": dir_return, "atr_rr": atr_rr, "dconf": dconf}
        all_dir.append(row)
        if decision.status in ACTIONABLE:
            by_tier[decision.status.value].append(row)
            bucket = "conf>=0.60" if dconf >= 0.60 else ("0.55-0.60" if dconf >= 0.55 else "<0.55")
            by_conf[bucket].append(row)

        if (n + 1) % 200 == 0:
            print(f"  {n + 1}/{len(sample_idx)}", flush=True)

    print("\n=== edge baseline: ALL directional ensemble signals (any status) ===", flush=True)
    print("  " + _summary(all_dir, cost), flush=True)

    print("\n=== actionable signals by decision tier ===", flush=True)
    for tier in ("RECOMMENDED", "WEAK_RECOMMENDATION"):
        print(f"  {tier:20} " + _summary(by_tier.get(tier, []), cost), flush=True)
    combined = by_tier.get("RECOMMENDED", []) + by_tier.get("WEAK_RECOMMENDATION", [])
    print(f"  {'COMBINED actionable':20} " + _summary(combined, cost), flush=True)

    print("\n=== actionable signals by directional-confidence bucket ===", flush=True)
    for bucket in ("<0.55", "0.55-0.60", "conf>=0.60"):
        print(f"  {bucket:12} " + _summary(by_conf.get(bucket, []), cost), flush=True)

    print("\nNote: expectancy is per-trade % move in the signal direction, net of cost.", flush=True)
    print("Positive expectancy + hit>50% (or PF>1) => the signals carry a real edge.", flush=True)


if __name__ == "__main__":
    main()
