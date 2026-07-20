r"""End-to-end check: run StrategyBrain.evaluate over recent windows and tally statuses.

Confirms the directional-confidence gate lets genuine signals through instead of
blocking everything as BLOCKED_BY_LOW_CONFIDENCE.
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gold_signal_system.config import ModelWeights, RuntimeConfig  # noqa: E402
from gold_signal_system.indicator_engine import FeatureIndicatorEngine  # noqa: E402
from gold_signal_system.model_ensemble import ModelEnsembleEngine  # noqa: E402
from gold_signal_system.strategy_brain import StrategyBrain, StrategyThresholdProfile  # noqa: E402
from training.dataset import load_candles, INFERENCE_WINDOW  # noqa: E402

SAMPLES = 150

runtime = RuntimeConfig()
TF = runtime.cycle_timeframe
engine = FeatureIndicatorEngine()
ens_engine = ModelEnsembleEngine(runtime=runtime, model_weights=ModelWeights())
profile = StrategyThresholdProfile(
    minimum_final_confidence=runtime.minimum_final_confidence,
    recommended_score=runtime.recommended_score,
    weak_recommendation_score=runtime.weak_recommendation_score,
)
brain = StrategyBrain(profile)
print(f"gate (minimum_final_confidence) = {profile.minimum_final_confidence}", flush=True)

candles = load_candles(runtime, TF)
sample_idx = list(range(INFERENCE_WINDOW - 1, len(candles)))[-SAMPLES:]

statuses: Counter = Counter()
non_hold = 0
dir_scores: list[float] = []
for n, i in enumerate(sample_idx):
    window = candles[i - (INFERENCE_WINDOW - 1): i + 1]
    features = engine.compute_features(window)
    snapshot = engine.build_indicator_snapshot(runtime.instrument, TF, window)
    votes = ens_engine.run_models(snapshot, features, prediction_time=datetime.now(tz=UTC), candles=window)
    ensemble = ens_engine.build_ensemble(votes)
    decision = brain.evaluate(ensemble, snapshot)
    statuses[decision.status.value] += 1
    if ensemble.ensemble_signal.value in ("BUY", "SELL"):
        non_hold += 1
        dir_scores.append(float(decision.score))
    if (n + 1) % 30 == 0:
        print(f"  {n + 1}/{len(sample_idx)}", flush=True)

print(f"\nnon-HOLD ensemble signals: {non_hold}/{len(sample_idx)}", flush=True)
print("decision status tally:", flush=True)
for status, count in statuses.most_common():
    print(f"  {status:30} {count:4}  ({count / len(sample_idx):.1%})", flush=True)

if dir_scores:
    import numpy as np
    s = np.array(dir_scores)
    print("\ntotal_score distribution (non-HOLD signals):", flush=True)
    print(f"  mean={s.mean():.1f} p50={np.median(s):.1f} p70={np.quantile(s, .70):.1f} "
          f"p85={np.quantile(s, .85):.1f} max={s.max():.1f}", flush=True)
    print(f"  thresholds in effect -> WEAK>={profile.weak_recommendation_score:.0f}, "
          f"RECOMMENDED>={profile.recommended_score:.0f}", flush=True)
