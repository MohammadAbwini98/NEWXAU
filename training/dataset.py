"""Build a supervised training dataset that matches runtime inference exactly.

At inference the pipeline feeds the last 300 candles of the cycle timeframe to
``compute_features`` / ``build_indicator_snapshot`` (see pipeline.run_signal_cycle),
then ``feature_vector_from_snapshot`` turns that into the 17-feature vector the
models receive. We replicate that per-sample here so the LightGBM features are
identical to what it will see live, and we build the standardized OHLC sequence
(via models/_nn_common.sequence_from_candles) for the neural models.

Label = forward return over ``horizon`` candles, bucketed into BUY/SELL/HOLD by
tercile thresholds so the classes stay balanced.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MODELS = ROOT / "models"
# NOTE: do not put MODELS on sys.path -- models/lightgbm.py would shadow the real
# lightgbm package. Load the shared adapter helpers by explicit file path instead.
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gold_signal_system.config import RuntimeConfig  # noqa: E402
from gold_signal_system.contracts import Candle  # noqa: E402
from gold_signal_system.indicator_engine import FeatureIndicatorEngine  # noqa: E402
from gold_signal_system.model_runtime import feature_vector_from_snapshot  # noqa: E402


def _load_nn_common():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_nn_common", str(MODELS / "_nn_common.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nn_common = _load_nn_common()

INFERENCE_WINDOW = 300  # pipeline.run_signal_cycle uses candle_store.get(limit=300)


@dataclass(slots=True)
class Dataset:
    X_tab: np.ndarray            # (N, 17) tabular features for LightGBM
    X_seq: np.ndarray            # (N, SEQ_LEN, C) standardized sequences
    y: np.ndarray                # (N,) class labels 0=BUY 1=SELL 2=HOLD
    times: np.ndarray            # (N,) candle index (chronological order preserved)
    buy_threshold: float
    sell_threshold: float
    meta: dict[str, Any] = field(default_factory=dict)


def load_candles(runtime: RuntimeConfig, timeframe: str) -> list[Candle]:
    import psycopg
    from psycopg.rows import dict_row

    schema = runtime.postgres_schema or "public"
    sql = (
        f'SELECT candle_time, open, high, low, close, volume '
        f'FROM "{schema}".market_candles '
        f'WHERE instrument=%s AND timeframe=%s ORDER BY candle_time ASC'
    )
    with psycopg.connect(runtime.postgres_dsn, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (runtime.instrument, timeframe))
            rows = cur.fetchall()

    candles: list[Candle] = []
    for r in rows:
        try:
            candles.append(
                Candle(
                    instrument=runtime.instrument,
                    timeframe=timeframe,
                    candle_time=r["candle_time"],
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    volume=float(r["volume"]) if r["volume"] is not None else 0.0,
                )
            )
        except Exception:
            continue
    return candles


def build_dataset(
    timeframe: str = "5m",
    horizon: int = 6,
    max_samples: int = 40_000,
    lower_q: float = 1 / 3,
    upper_q: float = 2 / 3,
    cache_path: str | None = None,
) -> Dataset:
    runtime = RuntimeConfig()
    engine = FeatureIndicatorEngine()

    candles = load_candles(runtime, timeframe)
    n = len(candles)
    print(f"[dataset] loaded {n} {timeframe} candles", flush=True)
    if n < INFERENCE_WINDOW + horizon + 10:
        raise SystemExit(f"Not enough candles ({n}); backfill more history first.")

    closes = np.array([c.close for c in candles], dtype=np.float64)

    # Eligible indices: full 300-candle lookback available AND horizon ahead exists.
    eligible = list(range(INFERENCE_WINDOW - 1, n - horizon))
    if len(eligible) > max_samples:
        stride = len(eligible) / max_samples
        eligible = [eligible[int(i * stride)] for i in range(max_samples)]
    print(f"[dataset] building {len(eligible)} samples (window={INFERENCE_WINDOW}, horizon={horizon})", flush=True)

    # Forward returns -> tercile thresholds for balanced labels.
    fwd_returns = np.array([closes[i + horizon] / closes[i] - 1.0 for i in eligible])
    buy_threshold = float(np.quantile(fwd_returns, upper_q))
    sell_threshold = float(np.quantile(fwd_returns, lower_q))
    print(f"[dataset] thresholds: buy>={buy_threshold:.5f} sell<={sell_threshold:.5f}", flush=True)

    X_tab: list[list[float]] = []
    X_seq: list[list[list[float]]] = []
    y: list[int] = []
    idx_kept: list[int] = []

    t0 = time.time()
    for k, i in enumerate(eligible):
        window = candles[i - (INFERENCE_WINDOW - 1): i + 1]
        window_dicts = [
            {"open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume or 0.0}
            for c in window
        ]
        seq = nn_common.sequence_from_candles(window_dicts, nn_common.SEQ_LEN)
        if seq is None:
            continue
        try:
            features = engine.compute_features(window)
            snapshot = engine.build_indicator_snapshot(runtime.instrument, timeframe, window)
            fv = feature_vector_from_snapshot(features, snapshot.raw_json)
        except Exception:
            continue

        label = nn_common.make_label(fwd_returns[k], buy_threshold, sell_threshold)
        X_tab.append(fv)
        X_seq.append(seq)
        y.append(label)
        idx_kept.append(i)

        if (k + 1) % 5000 == 0:
            rate = (k + 1) / (time.time() - t0)
            print(f"[dataset]   {k + 1}/{len(eligible)} ({rate:.0f}/s)", flush=True)

    ds = Dataset(
        X_tab=np.asarray(X_tab, dtype=np.float32),
        X_seq=np.asarray(X_seq, dtype=np.float32),
        y=np.asarray(y, dtype=np.int64),
        times=np.asarray(idx_kept, dtype=np.int64),
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
        meta={
            "timeframe": timeframe,
            "horizon": horizon,
            "window": INFERENCE_WINDOW,
            "seq_len": nn_common.SEQ_LEN,
            "n_channels": nn_common.N_CHANNELS,
            "instrument": runtime.instrument,
        },
    )
    counts = np.bincount(ds.y, minlength=3).tolist()
    print(f"[dataset] built {len(ds.y)} samples | class counts buy/sell/hold = {counts}", flush=True)

    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            cache_path,
            X_tab=ds.X_tab, X_seq=ds.X_seq, y=ds.y, times=ds.times,
            buy_threshold=ds.buy_threshold, sell_threshold=ds.sell_threshold,
        )
        print(f"[dataset] cached -> {cache_path}", flush=True)

    return ds


if __name__ == "__main__":
    build_dataset(cache_path=str(ROOT / "training" / "_cache" / "dataset_5m.npz"))
