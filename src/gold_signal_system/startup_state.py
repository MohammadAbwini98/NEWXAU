from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ModelWeights, RiskLimits, RuntimeConfig


def _setting_value(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    value = record.get("setting_value_json") or record.get("setting_value") or {}
    return value if isinstance(value, dict) else {}


def bootstrap_runtime_state(system, optimization_service, runtime: RuntimeConfig) -> dict[str, Any]:
    """Reload persistent state and clean incomplete jobs before runtime tasks start."""

    result: dict[str, Any] = {
        "loaded_active_optimization_profile": None,
        "loaded_optimization_runs": 0,
        "loaded_active_model_weight_profile": None,
        "loaded_system_settings": 0,
        "loaded_health_snapshots": 0,
        "loaded_latest_market_state": None,
        "marked_interrupted_jobs": 0,
        "imported_backtest_reports": {},
        "started_at": datetime.now(tz=UTC).isoformat(),
    }

    try:
        result["marked_interrupted_jobs"] = system.storage.mark_interrupted_backtest_jobs()
        result["imported_backtest_reports"] = system.storage.import_backtest_reports(runtime.reports_dir)

        settings = system.storage.list_settings()
        result["loaded_system_settings"] = settings.get("total", 0)

        weights = _setting_value(system.storage.get_setting("model_weights.active"))
        if weights:
            configured_weights = {str(k): float(v) for k, v in weights.items()}
            system.configured_model_weights = ModelWeights(weights=configured_weights)
            system.model_engine.model_weights = ModelWeights(weights=configured_weights)

        risk_limits = _setting_value(system.storage.get_setting("risk_limits.active"))
        if risk_limits:
            current = RiskLimits()
            for key, value in risk_limits.items():
                if hasattr(current, key):
                    setattr(current, key, value)
            system.risk_engine = system.risk_engine.__class__(current)

        model_weight_state = system.storage.load_model_weight_state()
        active_weights = model_weight_state.get("weights") or model_weight_state.get("weights_json") or {}
        if active_weights:
            system.model_engine.model_weights = ModelWeights(weights={str(k): float(v) for k, v in active_weights.items()})
            system.dynamic_weight_service._last_effective_weights = dict(system.model_engine.model_weights.weights)
            result["loaded_active_model_weight_profile"] = model_weight_state.get("profile_id", "active")
        else:
            system.storage.save_model_weight_state(
                weights=dict(system.model_engine.model_weights.weights),
                reason="default_profile_created_on_startup",
            )
            result["loaded_active_model_weight_profile"] = "default-created"

        optimization_reload = optimization_service.reload_from_storage()
        active_profile = optimization_service.active_profile()
        result["loaded_active_optimization_profile"] = active_profile.get("name")
        result["loaded_optimization_runs"] = optimization_reload.get("runs", 0)

        latest_health = system.storage.get_latest_health_snapshot()
        result["loaded_health_snapshots"] = 1 if latest_health else 0

        system.storage.save_health_snapshot("startup", "HEALTHY", result)
    except Exception as exc:
        result["error"] = str(exc)
        try:
            system.storage.save_health_event("startup", "CRITICAL", f"Persistent state reload failed: {exc}", result)
        except Exception:
            pass

    print(f"Loaded active optimization profile: {result.get('loaded_active_optimization_profile')}")
    print(f"Loaded optimization runs: {result.get('loaded_optimization_runs', 0)}")
    print(f"Loaded active model weight profile: {result.get('loaded_active_model_weight_profile')}")
    print(f"Loaded system settings: {result.get('loaded_system_settings', 0)}")
    print(f"Loaded health snapshots: {result.get('loaded_health_snapshots', 0)}")
    print("Live price state: in-memory only")
    print(f"Marked interrupted jobs: {result.get('marked_interrupted_jobs', 0)}")
    imported = result.get("imported_backtest_reports", {})
    if isinstance(imported, dict):
        print(f"Loaded {imported.get('loaded_from_db', 0)} backtest runs from PostgreSQL.")
        print(f"Imported {imported.get('walk_forward', 0)} walk-forward reports from {Path(runtime.reports_dir) / 'walk_forward'}.")
        print(f"Imported {imported.get('backtests', 0)} backtest reports from {Path(runtime.reports_dir) / 'backtests'}.")

    return result
