r"""Validate that the trained models are genuinely diverse and lift ensemble confidence.

Runs the real runtime path (ModelEnsembleEngine.run_models + build_ensemble) over a
set of recent candle windows, then reports:
  * per-model BUY-probability pairwise correlation (are they still clones?)
  * ensemble confidence distribution and the fraction that clears the 0.55 gate

Usage:
    .\.venv\Scripts\python.exe scripts\validate_models.py --samples 120
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gold_signal_system.config import ModelWeights, RuntimeConfig  # noqa: E402
from gold_signal_system.indicator_engine import FeatureIndicatorEngine  # noqa: E402
from gold_signal_system.model_ensemble import ModelEnsembleEngine  # noqa: E402
from training.dataset import load_candles, INFERENCE_WINDOW  # noqa: E402

MODEL_ORDER = ["KRONOS", "TCN", "LightGBM", "PATCHTST", "CNN_LSTM", "NHITS"]


def main() -> None:
    runtime = RuntimeConfig()
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframe", default=runtime.cycle_timeframe)
    ap.add_argument("--samples", type=int, default=120)
    ap.add_argument("--gate", type=float, default=0.55)
    args = ap.parse_args()

    engine = FeatureIndicatorEngine()
    ensemble_engine = ModelEnsembleEngine(runtime=runtime, model_weights=ModelWeights())

    candles = load_candles(runtime, args.timeframe)
    print(f"loaded {len(candles)} candles", flush=True)
    eligible = list(range(INFERENCE_WINDOW - 1, len(candles)))
    sample_idx = eligible[-args.samples:]

    per_model_buy: dict[str, list[float]] = {m: [] for m in MODEL_ORDER}
    ens_conf: list[float] = []
    dir_conf: list[float] = []   # directional confidence for non-HOLD signals
    ens_pass = 0

    for n, i in enumerate(sample_idx):
        window = candles[i - (INFERENCE_WINDOW - 1): i + 1]
        features = engine.compute_features(window)
        snapshot = engine.build_indicator_snapshot(runtime.instrument, args.timeframe, window)
        votes = ensemble_engine.run_models(snapshot, features, prediction_time=datetime.now(tz=UTC), candles=window)
        for v in votes:
            per_model_buy.setdefault(v.model_name, []).append(v.buy_probability)
        ens = ensemble_engine.build_ensemble(votes)
        ens_conf.append(ens.ensemble_confidence)
        if ens.ensemble_confidence >= args.gate:
            ens_pass += 1
        # Directional confidence = winning side share among BUY/SELL (ignores HOLD mass).
        directional_total = ens.buy_score + ens.sell_score
        sig = ens.ensemble_signal.value
        if sig in ("BUY", "SELL") and directional_total > 0:
            win = ens.buy_score if sig == "BUY" else ens.sell_score
            dir_conf.append(win / directional_total)
        if (n + 1) % 30 == 0:
            print(f"  {n + 1}/{len(sample_idx)}", flush=True)

    print("\n=== per-model BUY-probability stats ===", flush=True)
    names = [m for m in per_model_buy if per_model_buy[m]]
    for m in names:
        arr = np.array(per_model_buy[m])
        print(f"  {m:10} mean={arr.mean():.3f} std={arr.std():.3f}", flush=True)

    print("\n=== pairwise correlation of BUY probabilities (lower = more diverse) ===", flush=True)
    mat = np.array([per_model_buy[m] for m in names])
    corr = np.corrcoef(mat)
    header = "          " + "".join(f"{m[:7]:>9}" for m in names)
    print(header, flush=True)
    for r, m in enumerate(names):
        row = "".join(f"{corr[r, c]:>9.2f}" for c in range(len(names)))
        print(f"  {m[:8]:9}{row}", flush=True)

    # Average off-diagonal correlation as a single diversity score.
    off = corr[~np.eye(len(names), dtype=bool)]
    print(f"\n  mean off-diagonal correlation = {off.mean():.3f}", flush=True)

    ens_conf_arr = np.array(ens_conf)
    print("\n=== ensemble confidence (3-class max, current gate metric) ===", flush=True)
    print(f"  mean={ens_conf_arr.mean():.3f} min={ens_conf_arr.min():.3f} max={ens_conf_arr.max():.3f}", flush=True)
    print(f"  fraction >= {args.gate} gate: {ens_pass}/{len(ens_conf)} = {ens_pass / len(ens_conf):.1%}", flush=True)

    if dir_conf:
        dc = np.array(dir_conf)
        print("\n=== directional confidence (winning side / (buy+sell)) ===", flush=True)
        print(f"  n={len(dc)} non-HOLD signals | mean={dc.mean():.3f} "
              f"median={np.median(dc):.3f} p25={np.quantile(dc, .25):.3f} p75={np.quantile(dc, .75):.3f}", flush=True)
        print("  pass rate at candidate gates:", flush=True)
        for g in (0.50, 0.52, 0.55, 0.58, 0.60):
            frac = float((dc >= g).mean())
            print(f"    gate {g:.2f}: {frac:.1%}", flush=True)


if __name__ == "__main__":
    main()
