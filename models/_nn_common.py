"""Shared sequence representation + neural architectures for the runtime models.

Both the training pipeline (scripts/train_models.py) and the runtime adapters
(models/tcn.py, patchtst.py, cnn_lstm.py, nhits.py) import from this module so
that the input representation is *identical* at train and inference time.

Class index convention (matches gold_signal_system.model_runtime._normalize_three,
which reads probability vectors as [buy, sell, hold]):
    0 -> BUY
    1 -> SELL
    2 -> HOLD
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

SEQ_LEN = 96          # timesteps fed to the sequence models
N_CHANNELS = 10       # per-timestep engineered features (see sequence_from_candles)
WARMUP = 64           # extra leading candles used to warm up indicators (then trimmed)
N_CLASSES = 3         # BUY / SELL / HOLD
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"

CLASS_BUY, CLASS_SELL, CLASS_HOLD = 0, 1, 2


# ---------------------------------------------------------------------------
# Input representation (pure python so it works with or without numpy)
# ---------------------------------------------------------------------------
def _roll_mean(x, w: int):
    import numpy as np

    c = np.concatenate(([0.0], np.cumsum(x)))
    out = np.empty_like(x, dtype=np.float64)
    for i in range(len(x)):
        lo = max(0, i - w + 1)
        out[i] = (c[i + 1] - c[lo]) / (i - lo + 1)
    return out


def _ema_series(x, period: int):
    import numpy as np

    k = 2.0 / (period + 1.0)
    out = np.empty_like(x, dtype=np.float64)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1.0 - k)
    return out


def _rsi_series(close, period: int = 14):
    import numpy as np

    delta = np.diff(close, prepend=close[0])
    gain = np.clip(delta, 0.0, None)
    loss = np.clip(-delta, 0.0, None)
    rs = _roll_mean(gain, period) / np.maximum(_roll_mean(loss, period), 1e-12)
    return 100.0 - 100.0 / (1.0 + rs)


def _atr_series(high, low, close, period: int = 14):
    import numpy as np

    prev_c = np.roll(close, 1)
    prev_c[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_c), np.abs(low - prev_c)))
    return _roll_mean(tr, period)


def _macd_hist_series(close):
    macd = _ema_series(close, 12) - _ema_series(close, 26)
    return macd - _ema_series(macd, 9)


def sequence_from_candles(candles: list[dict[str, Any]], seq_len: int = SEQ_LEN):
    """Build a (seq_len, N_CHANNELS) standardized sequence of engineered features.

    Channels (computed causally, then per-window z-scored so price level / scale
    don't matter):
      0 log return of close        5 5-bar log return (momentum)
      1 body / range               6 RSI(14)
      2 upper wick / range         7 MACD histogram / close
      3 lower wick / range         8 ATR(14) / close (volatility regime)
      4 volume                     9 (close - EMA20) / close (trend deviation)

    Uses up to seq_len+WARMUP candles to warm up the indicators, then emits the
    last seq_len timesteps. Returns None if too few candles.
    """
    import numpy as np

    if len(candles) < seq_len + 1:
        return None
    rows = candles[-(seq_len + WARMUP):]

    o = np.array([float(r["open"]) for r in rows], dtype=np.float64)
    h = np.array([float(r["high"]) for r in rows], dtype=np.float64)
    low = np.array([float(r["low"]) for r in rows], dtype=np.float64)
    c = np.array([float(r["close"]) for r in rows], dtype=np.float64)
    v = np.array([float(r.get("volume") or 0.0) for r in rows], dtype=np.float64)
    eps = 1e-9
    cpos = np.maximum(c, eps)

    r1 = np.zeros_like(c)
    r1[1:] = np.log(cpos[1:] / cpos[:-1])
    r5 = np.zeros_like(c)
    r5[5:] = np.log(cpos[5:] / cpos[:-5])
    rng = np.maximum(h - low, eps)
    body = (c - o) / rng
    upper_wick = (h - np.maximum(o, c)) / rng
    lower_wick = (np.minimum(o, c) - low) / rng
    rsi = _rsi_series(c, 14)
    macd_hist = _macd_hist_series(c) / cpos
    atr_pct = _atr_series(h, low, c, 14) / cpos
    dist_ema = (c - _ema_series(c, 20)) / cpos

    feats = np.stack(
        [r1, body, upper_wick, lower_wick, v, r5, rsi, macd_hist, atr_pct, dist_ema],
        axis=1,
    )[-seq_len:]

    mean = feats.mean(axis=0)
    std = feats.std(axis=0)
    std[std < 1e-9] = 1.0
    return ((feats - mean) / std).astype(np.float32)  # (seq_len, N_CHANNELS)


def make_label(forward_return: float, buy_threshold: float, sell_threshold: float) -> int:
    if forward_return >= buy_threshold:
        return CLASS_BUY
    if forward_return <= sell_threshold:
        return CLASS_SELL
    return CLASS_HOLD


# ---------------------------------------------------------------------------
# Architectures (torch imported lazily so importing this module is cheap)
# ---------------------------------------------------------------------------
def _torch():
    import torch  # noqa: F401
    import torch.nn as nn  # noqa: F401

    return torch, nn


def build_model(kind: str):
    """Instantiate one of the four architectures by name."""
    torch, nn = _torch()
    kind = kind.lower()

    class TCN(nn.Module):
        def __init__(self, c_in=N_CHANNELS, ch=48, levels=4, k=3):
            super().__init__()
            layers = []
            prev = c_in
            for i in range(levels):
                d = 2 ** i
                pad = (k - 1) * d
                layers += [
                    nn.Conv1d(prev, ch, k, padding=pad, dilation=d),
                    nn.ReLU(),
                    nn.BatchNorm1d(ch),
                    nn.Dropout(0.1),
                ]
                prev = ch
            self.net = nn.Sequential(*layers)
            self.k = k
            self.head = nn.Linear(ch, N_CLASSES)

        def forward(self, x):  # x: (B, T, C)
            z = x.transpose(1, 2)  # (B, C, T)
            z = self.net(z)
            z = z[:, :, : x.size(1)]  # causal trim
            z = z.mean(dim=2)  # global average pool
            return self.head(z)

    class CNNLSTM(nn.Module):
        def __init__(self, c_in=N_CHANNELS, ch=32, hidden=48):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(c_in, ch, 3, padding=1), nn.ReLU(),
                nn.Conv1d(ch, ch, 3, padding=1), nn.ReLU(),
            )
            self.lstm = nn.LSTM(ch, hidden, batch_first=True, num_layers=1)
            self.head = nn.Sequential(nn.Dropout(0.1), nn.Linear(hidden, N_CLASSES))

        def forward(self, x):  # (B, T, C)
            z = self.conv(x.transpose(1, 2)).transpose(1, 2)  # (B, T, ch)
            out, _ = self.lstm(z)
            return self.head(out[:, -1, :])

    class PatchTST(nn.Module):
        def __init__(self, c_in=N_CHANNELS, patch=8, d_model=64, heads=4, layers=2, seq_len=SEQ_LEN):
            super().__init__()
            self.patch = patch
            self.n_patches = seq_len // patch
            self.embed = nn.Linear(patch * c_in, d_model)
            self.pos = nn.Parameter(torch.zeros(1, self.n_patches, d_model))
            enc = nn.TransformerEncoderLayer(
                d_model, heads, dim_feedforward=d_model * 2, dropout=0.1, batch_first=True
            )
            self.encoder = nn.TransformerEncoder(enc, num_layers=layers)
            self.head = nn.Linear(d_model, N_CLASSES)

        def forward(self, x):  # (B, T, C)
            b, t, c = x.shape
            usable = self.n_patches * self.patch
            x = x[:, t - usable:, :]
            z = x.reshape(b, self.n_patches, self.patch * c)
            z = self.embed(z) + self.pos
            z = self.encoder(z)
            return self.head(z.mean(dim=1))

    class NHiTS(nn.Module):
        """Classification variant: hierarchical multi-rate pooling MLP stack."""

        def __init__(self, c_in=N_CHANNELS, seq_len=SEQ_LEN, hidden=64, rates=(1, 2, 4)):
            super().__init__()
            self.rates = rates
            self.blocks = nn.ModuleList()
            for r in rates:
                pooled = seq_len // r
                self.blocks.append(
                    nn.Sequential(
                        nn.Linear(pooled * c_in, hidden), nn.ReLU(),
                        nn.Linear(hidden, hidden), nn.ReLU(),
                    )
                )
            self.head = nn.Sequential(nn.Dropout(0.1), nn.Linear(hidden * len(rates), N_CLASSES))

        def forward(self, x):  # (B, T, C)
            b, t, c = x.shape
            feats = []
            for r, block in zip(self.rates, self.blocks):
                pooled = t // r
                z = x[:, t - pooled * r:, :]
                if r > 1:
                    z = z.transpose(1, 2)  # (B, C, T)
                    z = torch.nn.functional.avg_pool1d(z, kernel_size=r)  # (B, C, pooled)
                    z = z.transpose(1, 2)  # (B, pooled, C)
                feats.append(block(z.reshape(b, -1)))
            return self.head(torch.cat(feats, dim=1))

    factory = {"tcn": TCN, "cnn_lstm": CNNLSTM, "patchtst": PatchTST, "nhits": NHiTS}
    if kind not in factory:
        raise ValueError(f"Unknown model kind: {kind}")
    return factory[kind]()


# ---------------------------------------------------------------------------
# Inference helper used by the runtime adapters
# ---------------------------------------------------------------------------
_LOADED: dict[str, Any] = {}


def predict_sequence_probs(kind: str, candles: list[dict[str, Any]]) -> tuple[float, float, float] | None:
    """Load (cached) the trained weights for ``kind`` and return (buy, sell, hold).

    Returns None if weights are missing or the sequence cannot be built, so the
    caller can fall back to the heuristic.
    """
    seq = sequence_from_candles(candles, SEQ_LEN)
    if seq is None:
        return None

    weights_path = WEIGHTS_DIR / f"{kind}.pt"
    if not weights_path.exists():
        return None

    torch, _ = _torch()
    model = _LOADED.get(kind)
    if model is None:
        model = build_model(kind)
        state = torch.load(str(weights_path), map_location="cpu")
        model.load_state_dict(state)
        model.eval()
        _LOADED[kind] = model

    with torch.no_grad():
        x = torch.from_numpy(seq).unsqueeze(0).float()  # (1, T, C)
        logits = model(x)
        probs = torch.softmax(logits, dim=1)[0].tolist()

    buy, sell, hold = float(probs[CLASS_BUY]), float(probs[CLASS_SELL]), float(probs[CLASS_HOLD])
    return buy, sell, hold
