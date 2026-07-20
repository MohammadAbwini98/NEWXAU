r"""Train real models to replace the placeholder heuristic adapters.

Produces (all under models/):
    lightgbm.joblib          -> supersedes models/lightgbm.py via the artifact loader
    weights/tcn.pt           -> loaded by the rewritten models/tcn.py adapter
    weights/cnn_lstm.pt      -> loaded by models/cnn_lstm.py
    weights/patchtst.pt      -> loaded by models/patchtst.py
    weights/nhits.pt         -> loaded by models/nhits.py
    _training_meta.json      -> thresholds, split sizes, validation metrics

Split is chronological (no shuffle) to avoid look-ahead leakage. Usage:
    .\.venv\Scripts\python.exe scripts\train_models.py --max-samples 40000 --epochs 14
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MODELS = ROOT / "models"
# Do not add MODELS to sys.path (models/lightgbm.py would shadow the real package).
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from training.dataset import build_dataset, Dataset  # noqa: E402

nn_common = build_dataset.__globals__["nn_common"]  # reuse the file-path-loaded module

WEIGHTS_DIR = MODELS / "weights"
NEURAL_KINDS = ("tcn", "cnn_lstm", "patchtst", "nhits")
CLASS_NAMES = ["BUY", "SELL", "HOLD"]


def _split(n: int, val_frac: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    cut = int(n * (1 - val_frac))
    idx = np.arange(n)
    return idx[:cut], idx[cut:]


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, probs: np.ndarray) -> dict:
    acc = float((y_true == y_pred).mean())
    # mean confidence = mean of winning-class probability (proxy for ensemble lift)
    mean_conf = float(probs.max(axis=1).mean())
    per_class = {}
    for c, name in enumerate(CLASS_NAMES):
        mask = y_true == c
        per_class[name] = round(float((y_pred[mask] == c).mean()), 3) if mask.any() else None
    return {"val_acc": round(acc, 4), "val_mean_conf": round(mean_conf, 4), "recall": per_class}


def train_lightgbm(ds: Dataset, tr: np.ndarray, va: np.ndarray) -> dict:
    import joblib
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation

    clf = LGBMClassifier(
        objective="multiclass",
        num_class=3,
        n_estimators=600,
        learning_rate=0.03,
        num_leaves=31,
        max_depth=-1,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        min_child_samples=50,
        class_weight="balanced",
        n_jobs=-1,
        verbose=-1,
    )
    clf.fit(
        ds.X_tab[tr], ds.y[tr],
        eval_set=[(ds.X_tab[va], ds.y[va])],
        eval_metric="multi_logloss",
        callbacks=[early_stopping(40, verbose=False), log_evaluation(0)],
    )
    out = MODELS / "lightgbm.joblib"
    joblib.dump(clf, out)
    probs = clf.predict_proba(ds.X_tab[va])
    m = _metrics(ds.y[va], probs.argmax(axis=1), probs)
    m["artifact"] = str(out.relative_to(ROOT))
    m["best_iteration"] = int(getattr(clf, "best_iteration_", 0) or 0)
    print(f"[lightgbm] {m}", flush=True)
    return m


def train_neural(kind: str, ds: Dataset, tr: np.ndarray, va: np.ndarray, epochs: int, batch: int) -> dict:
    import torch
    import torch.nn as nn

    torch.manual_seed(1337)
    model = nn_common.build_model(kind)
    Xtr = torch.tensor(ds.X_seq[tr]); ytr = torch.tensor(ds.y[tr])
    Xva = torch.tensor(ds.X_seq[va]); yva = torch.tensor(ds.y[va])

    counts = np.bincount(ds.y[tr], minlength=3).astype(np.float64)
    weights = torch.tensor((counts.sum() / (3 * np.maximum(counts, 1))), dtype=torch.float32)
    loss_fn = nn.CrossEntropyLoss(weight=weights)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)

    n = len(tr)
    best_acc, best_state = -1.0, None
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n)
        for s in range(0, n, batch):
            b = perm[s: s + batch]
            opt.zero_grad()
            loss = loss_fn(model(Xtr[b]), ytr[b])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            va_logits = model(Xva)
            va_pred = va_logits.argmax(dim=1)
            acc = float((va_pred == yva).float().mean())
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    out = WEIGHTS_DIR / f"{kind}.pt"
    torch.save(model.state_dict(), out)

    model.eval()
    with torch.no_grad():
        probs = torch.softmax(model(Xva), dim=1).numpy()
    m = _metrics(ds.y[va], probs.argmax(axis=1), probs)
    m["artifact"] = str(out.relative_to(ROOT))
    print(f"[{kind}] {m}", flush=True)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframe", default="5m")
    ap.add_argument("--horizon", type=int, default=6)
    ap.add_argument("--max-samples", type=int, default=40_000)
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--val-frac", type=float, default=0.2)
    args = ap.parse_args()

    t0 = time.time()
    cache = ROOT / "training" / "_cache" / f"dataset_{args.timeframe}_h{args.horizon}.npz"
    ds = build_dataset(
        timeframe=args.timeframe, horizon=args.horizon,
        max_samples=args.max_samples, cache_path=str(cache),
    )
    tr, va = _split(len(ds.y), args.val_frac)
    print(f"[train] {len(tr)} train / {len(va)} val samples", flush=True)

    results: dict[str, dict] = {}
    results["lightgbm"] = train_lightgbm(ds, tr, va)
    for kind in NEURAL_KINDS:
        results[kind] = train_neural(kind, ds, tr, va, args.epochs, args.batch)

    meta = {
        "timeframe": args.timeframe,
        "horizon": args.horizon,
        "buy_threshold": ds.buy_threshold,
        "sell_threshold": ds.sell_threshold,
        "n_samples": int(len(ds.y)),
        "n_train": int(len(tr)),
        "n_val": int(len(va)),
        "seq_len": nn_common.SEQ_LEN,
        "n_channels": nn_common.N_CHANNELS,
        "results": results,
        "trained_seconds": round(time.time() - t0, 1),
    }
    (MODELS / "_training_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[train] DONE in {meta['trained_seconds']}s -> models/_training_meta.json", flush=True)


if __name__ == "__main__":
    main()
