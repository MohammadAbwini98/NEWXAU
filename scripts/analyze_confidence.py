r"""Diagnose per-model confidence + calibration on the cached 1h holdout.

Answers: are the trained models' low-confidence outputs honest (well-calibrated on
a hard target) or underconfident (accuracy >> confidence => room to sharpen)?
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
MODELS = ROOT / "models"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_nn_common():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_nn_common", str(MODELS / "_nn_common.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


nn_common = _load_nn_common()

cache = ROOT / "training" / "_cache" / "dataset_1h_h8.npz"
d = np.load(cache)
X_tab, X_seq, y = d["X_tab"], d["X_seq"], d["y"]
cut = int(len(y) * 0.8)
Xtab_v, Xseq_v, yv = X_tab[cut:], X_seq[cut:], y[cut:]
print(f"holdout: {len(yv)} samples (chronological last 20%)\n")


def report(name: str, probs: np.ndarray) -> None:
    pred = probs.argmax(axis=1)
    conf = probs.max(axis=1)
    acc = (pred == yv).mean()
    print(f"{name:10} mean_conf={conf.mean():.3f}  acc={acc:.3f}  conf_std={conf.std():.3f}")
    # Calibration: accuracy within confidence quartiles.
    qs = np.quantile(conf, [0.25, 0.5, 0.75])
    bins = np.digitize(conf, qs)
    parts = []
    for b in range(4):
        m = bins == b
        if m.any():
            parts.append(f"Q{b+1}(conf~{conf[m].mean():.2f}):acc={ (pred[m]==yv[m]).mean():.2f}")
    print("           " + "  ".join(parts))


# LightGBM
import joblib  # noqa: E402
lgb = joblib.load(MODELS / "lightgbm.joblib")
report("LightGBM", lgb.predict_proba(Xtab_v))

# Neural models
import torch  # noqa: E402
for kind in ("tcn", "cnn_lstm", "patchtst", "nhits"):
    model = nn_common.build_model(kind)
    model.load_state_dict(torch.load(str(MODELS / "weights" / f"{kind}.pt"), map_location="cpu"))
    model.eval()
    with torch.no_grad():
        probs = torch.softmax(model(torch.tensor(Xseq_v)), dim=1).numpy()
    report(kind, probs)

print(f"\nrandom-baseline accuracy = {max(np.bincount(yv)) / len(yv):.3f} (majority) / 0.333 (uniform)")
print("Interpretation: if acc rises with confidence quartile, confidence is meaningful")
print("(honest, just low). If high-conf acc is flat/near-random, the model is noisy.")
