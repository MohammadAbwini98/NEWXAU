from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system import api
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.walk_forward import WalkForwardBacktestService


class BacktestDashboardFixTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            reports_dir=self.tmp.name,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            live_candle_lookback=300,
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.walk_forward_service = WalkForwardBacktestService(api.system, reports_dir=runtime.reports_dir)
        api.latest_price_tick = None
        api.latest_price_stream_status = {"status": "WAITING_FOR_STREAM"}

    def tearDown(self) -> None:
        if hasattr(api.system.storage, "close"):
            api.system.storage.close()
        self.tmp.cleanup()

    async def test_no_backtest_run_state_is_clear(self) -> None:
        summary = await api.get_backtest_summary()

        self.assertEqual(summary["status"], "NO_BACKTEST_RUN")
        self.assertIn("POST /api/backtests/run", summary["next_action"])

    async def test_backtest_status_reports_running_progress(self) -> None:
        api.system.storage.create_backtest_run(
            "BT-RUNNING",
            "WALK_FORWARD",
            "XAUUSD",
            "5m",
            {"synthetic_count": 120, "train_size": 90, "test_size": 20, "step_size": 20},
            status="RUNNING",
        )

        status = await api.get_backtest_status()

        self.assertEqual(status["run_id"], "BT-RUNNING")
        self.assertTrue(status["active"])
        self.assertEqual(status["status"], "RUNNING")
        self.assertGreaterEqual(status["progress"], 5)

    async def test_post_backtest_run_persists_run_reports_folds_and_trades(self) -> None:
        result = await api.run_backtest(
            {
                "run_type": "WALK_FORWARD",
                "instrument": "XAUUSD",
                "timeframe": "5m",
                "synthetic_count": 90,
                "train_size": 40,
                "test_size": 20,
                "step_size": 20,
                "min_window": 30,
                "model_mode": "MOCK_FOR_TEST_ONLY",
            }
        )

        self.assertEqual(result["status"], "COMPLETED")
        run_id = result["run_id"]
        runs = await api.list_walk_forward_backtests()
        self.assertIn(run_id, [item["run_id"] for item in runs["items"]])

        summary = await api.get_backtest_summary()
        self.assertEqual(summary["run_id"], run_id)
        self.assertEqual(summary["model_mode"], "MOCK_FOR_TEST_ONLY")

        report_dir = os.path.join(self.tmp.name, "walk_forward", run_id)
        for filename in ("summary.json", "folds.csv", "trades.csv", "metrics.json", "recommendations.md"):
            self.assertTrue(os.path.exists(os.path.join(report_dir, filename)), filename)

        folds = await api.get_walk_forward_windows(run_id)
        trades = await api.get_backtest_trades(run_id)
        self.assertGreaterEqual(folds["total"], 1)
        self.assertIn("total", trades)

        restored = GoldSignalSystem(runtime=api.runtime)
        try:
            restored.storage.import_backtest_reports(api.runtime.reports_dir)
            self.assertEqual(restored.storage.latest_backtest_summary()["run_id"], run_id)
        finally:
            if hasattr(restored.storage, "close"):
                restored.storage.close()

    def test_dashboard_has_backtest_button_and_endpoint_wiring(self) -> None:
        path = os.path.join(ROOT, "src", "gold_signal_system", "dashboard_static", "index.html")
        with open(path, encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("Run Walk-Forward Backtest", html)
        self.assertIn('/api/backtests/run', html)
        self.assertIn('/api/backtest/status', html)
        self.assertIn('Backtest Progress', html)
        self.assertIn('data-form="backtest-run"', html)
        self.assertIn('/api/backtest/summary', html)


if __name__ == "__main__":
    unittest.main()
