from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system import api
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.optimization import ThresholdOptimizationService
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.startup_state import bootstrap_runtime_state
from gold_signal_system.storage import InMemoryStorage
from gold_signal_system.walk_forward import WalkForwardBacktestService


class PersistentRuntimeStateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            latest_price_stale_seconds=30,
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.walk_forward_service = WalkForwardBacktestService(api.system, reports_dir=runtime.reports_dir)
        api.optimization_service = ThresholdOptimizationService(api.walk_forward_service, storage=api.system.storage)
        api.latest_price_tick = None
        api.latest_price_stream_status = {"status": "WAITING_FOR_STREAM"}

    async def test_settings_endpoints_save_to_storage(self) -> None:
        weights = await api.set_model_weights({"kronos": 0.3, "tcn": 0.25, "lightgbm": 0.2, "patchtst": 0.1, "cnn_lstm": 0.1, "nhits": 0.05})
        risk = await api.set_risk_limits({"max_spread": 0.33, "max_risk_per_trade_pct": 0.8})

        self.assertEqual(weights["status"], "OK")
        self.assertEqual(risk["status"], "OK")
        self.assertEqual(api.system.storage.get_setting("model_weights.active")["source"], "dashboard")
        self.assertEqual(api.system.storage.get_setting("risk_limits.active")["setting_value_json"]["max_spread"], 0.33)

    async def test_latest_market_state_is_not_reloaded_as_price(self) -> None:
        old_ts = datetime.now(tz=UTC) - timedelta(minutes=10)
        api.system.storage.save_latest_market_state(
            {
                "instrument": "XAUUSD",
                "bid": 65000.0,
                "ask": 65005.0,
                "mid": 65002.5,
                "spread": 0.4,
                "timestamp": old_ts.isoformat(),
                "stream_status": "LIVE",
                "source": "capital.com.websocket",
            }
        )

        payload = await api.get_latest_price()

        self.assertEqual(payload["status"], "DISABLED")
        self.assertIn("memory-only", payload["message"].lower())

    def test_optimization_runs_and_profiles_reload_from_storage(self) -> None:
        storage = InMemoryStorage()
        service = ThresholdOptimizationService(walk_forward_service=None, storage=storage)
        storage.save_optimization_profile(
            {
                "id": 2,
                "name": "candidate",
                "instrument": "XAUUSD",
                "timeframe": "5m",
                "parameters": {"minimum_final_confidence": 0.6},
                "is_active": True,
            }
        )
        storage.save_optimization_run(
            {"id": 1, "run_id": "OPT-TEST-001", "status": "COMPLETED", "summary": {"candidate_count": 1}},
            [{"id": 1, "profile_id": 2, "score": 80, "rank": 1}],
        )

        restarted = ThresholdOptimizationService(walk_forward_service=None, storage=storage)

        self.assertEqual(restarted.active_profile()["name"], "candidate")
        self.assertEqual(restarted.runs[0]["run_id"], "OPT-TEST-001")
        self.assertEqual(storage.get_optimization_candidates("OPT-TEST-001")["total"], 1)

    def test_model_weight_state_health_and_interrupted_jobs_persist(self) -> None:
        storage = InMemoryStorage()
        storage.save_model_weight_state({"kronos": 0.4, "tcn": 0.6}, history=[{"model_name": "kronos", "effective_weight": 0.4}], reason="test")
        storage.save_health_event("database", "CRITICAL", "Connection failed.", {"attempt": 1})
        storage.save_health_snapshot("database", "CRITICAL", {"attempt": 1}, failure_count=1)
        storage.create_backtest_run("BT-RUNNING", "BACKTEST", "XAUUSD", "5m", {}, status="RUNNING")

        self.assertEqual(storage.load_model_weight_state()["weights"]["kronos"], 0.4)
        self.assertEqual(storage.get_health_events()["total"], 1)
        self.assertEqual(storage.get_latest_health_snapshot()["status"], "CRITICAL")
        self.assertEqual(storage.mark_interrupted_backtest_jobs(), 1)
        self.assertEqual(storage.get_backtest_run("BT-RUNNING")["status"], "INTERRUPTED")

    def test_startup_bootstrap_loads_persistent_state(self) -> None:
        storage_runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None, enable_background_cycle_runner=False, enable_live_price_stream=False)
        system = GoldSignalSystem(runtime=storage_runtime)
        system.storage.save_setting("model_weights.active", {"kronos": 0.5, "tcn": 0.5}, setting_group="model_weights")
        system.storage.save_latest_market_state({"instrument": "XAUUSD", "mid": 65000, "timestamp": datetime.now(tz=UTC).isoformat()})
        service = ThresholdOptimizationService(WalkForwardBacktestService(system), storage=system.storage)

        result = bootstrap_runtime_state(system, service, storage_runtime)

        self.assertGreaterEqual(result["loaded_system_settings"], 1)
        self.assertIsNone(result["loaded_latest_market_state"])

    def test_dashboard_contains_clear_empty_states(self) -> None:
        path = os.path.join(ROOT, "src", "gold_signal_system", "dashboard_static", "index.html")
        with open(path, encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("No optimization run has been executed yet", html)
        self.assertIn("Using default model weights. No adaptive updates yet.", html)
        self.assertIn("No persisted health snapshot yet", html)


if __name__ == "__main__":
    unittest.main()
