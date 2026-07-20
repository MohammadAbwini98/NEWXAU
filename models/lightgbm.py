from __future__ import annotations

from _baseline_common import predict_with_profile


def predict_proba(feature_vector: list[float]) -> tuple[float, float, float]:
    return predict_with_profile(feature_vector, tilt=0.01, sensitivity=0.96, hold_bias=0.03)
