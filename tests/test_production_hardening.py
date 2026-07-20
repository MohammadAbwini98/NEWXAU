from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.dynamic_weights import DynamicModelWeightService
from gold_signal_system.news_filter import EconomicNewsEvent, EconomicNewsFilter, ManualNewsProvider, MockNewsProvider, build_news_provider
from gold_signal_system.optimization import ThresholdOptimizationService
from gold_signal_system.walk_forward import WalkForwardBacktestService, WalkForwardConfig

from test_improvement_services import _prediction


class ProductionHardeningTests(unittest.TestCase):
    def test_news_provider_modes_are_configurable(self) -> None:
        self.assertIsInstance(build_news_provider("mock"), MockNewsProvider)
        self.assertIsInstance(build_news_provider("manual"), ManualNewsProvider)

    def test_news_event_schema_has_event_id_and_block_window(self) -> None:
        now = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)
        provider = ManualNewsProvider()
        provider.add_event(
            EconomicNewsEvent(
                source="manual",
                event_name="US CPI",
                country="US",
                currency="USD",
                impact="HIGH",
                scheduled_at=now + timedelta(minutes=10),
                event_id="manual-cpi",
                block_before_minutes=30,
                block_after_minutes=30,
            )
        )
        risk = EconomicNewsFilter(provider=provider, block_before_minutes=30, block_after_minutes=30).current_risk(now)
        self.assertEqual(risk.status, "BLOCKED")
        self.assertEqual(risk.event["event_id"], "manual-cpi")

    def test_dynamic_weights_are_bounded_by_max_change(self) -> None:
        service = DynamicModelWeightService(max_change_per_update=0.03)
        first = service.calculate(
            {"kronos": 0.5, "tcn": 0.5},
            [_prediction("kronos"), _prediction("tcn")],
            {"kronos": {"observations": 10, "win_rate": 0.7, "buy_precision": 0.7}, "tcn": {"observations": 10, "win_rate": 0.3, "buy_precision": 0.3}},
        )
        first_weights = {item.model_name: item.effective_weight for item in first}
        second = service.calculate(
            {"kronos": 0.5, "tcn": 0.5},
            [_prediction("kronos"), _prediction("tcn")],
            {"kronos": {"observations": 10, "win_rate": 0.95, "buy_precision": 0.95}, "tcn": {"observations": 10, "win_rate": 0.1, "buy_precision": 0.1}},
        )
        second_weights = {item.model_name: item.effective_weight for item in second}
        self.assertLessEqual(abs(second_weights["kronos"] - first_weights["kronos"]), 0.06)
        self.assertGreaterEqual(len(service.profile_versions), 1)

    def test_walk_forward_writes_report_files(self) -> None:
        class FakeStorage:
            backtest_trades: list[dict] = []

        class FakePerformance:
            def metrics(self):
                return {}

        class FakeWeights:
            weights = {}

        class FakeSystem:
            storage = FakeStorage()
            performance_tracker = FakePerformance()
            model_engine = type("ModelEngine", (), {"model_weights": FakeWeights()})()

        with tempfile.TemporaryDirectory() as tmp:
            service = WalkForwardBacktestService(FakeSystem(), reports_dir=tmp)
            candles = [
                {"candle_time": f"2026-06-08T00:{idx:02d}:00Z", "open": 1, "high": 2, "low": 0, "close": 1, "volume": 0}
                for idx in range(40)
            ]
            windows = service.generate_windows(candles, WalkForwardConfig(train_size=10, test_size=5, step_size=5))
            for idx, window in enumerate(windows, start=1):
                window["window_id"] = idx
                window["summary"] = {"total_signals": 0, "win_rate": 0.0, "profit_factor": 0.0, "max_drawdown": 0.0, "average_rr": 0.0}
            report_dir = service._write_reports(
                {"id": 1, "config": {}, "summary": {"model_by_model": {}, "total_signals": 0}},
                windows,
            )
            for name in ("summary.json", "folds.csv", "trades.csv", "model_metrics.csv", "strategy_metrics.csv", "recommendations.md"):
                self.assertTrue((Path(report_dir) / name).exists())

    def test_threshold_profile_rollback(self) -> None:
        service = ThresholdOptimizationService(walk_forward_service=None)
        service.profiles.append(
            service.profiles[0].__class__(
                id=2,
                name="candidate",
                instrument="XAUUSD",
                timeframe="5m",
                parameters={"minimum_final_confidence": 0.7},
            )
        )
        self.assertEqual(service.activate(2)["status"], "OK")
        self.assertEqual(service.rollback()["status"], "OK")
        self.assertEqual(service.active_profile()["id"], 1)


if __name__ == "__main__":
    unittest.main()
