from __future__ import annotations

from typing import Any

from _baseline_common import predict_with_profile

import _nn_common as nn_common

_KIND = "nhits"
_FALLBACK = dict(tilt=0.00, sensitivity=0.92, hold_bias=0.05)


def predict_proba_market(feature_vector: list[float], context: dict[str, Any]) -> tuple[float, float, float]:
    """Run the trained N-HiTS on the candle sequence; fall back to the heuristic."""
    candles = (context or {}).get("candles") or []
    probs = nn_common.predict_sequence_probs(_KIND, candles)
    if probs is not None:
        return probs
    return predict_with_profile(feature_vector, **_FALLBACK)


def predict_proba(feature_vector: list[float]) -> tuple[float, float, float]:
    return predict_with_profile(feature_vector, **_FALLBACK)
