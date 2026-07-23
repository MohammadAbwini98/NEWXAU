from __future__ import annotations

import os
import sys
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.config import RuntimeConfig
from gold_signal_system.backtesting import BacktestConfig, BacktestingEngine
from gold_signal_system.contracts import MarketContext, SignalDirection
from gold_signal_system.data_engine import DataEngine
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.utils import generate_synthetic_candles


class DataQualityGateTests(unittest.TestCase):
    def test_quality_report_detects_integrity_and_freshness_failures(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        raw = generate_synthetic_candles(count=10, timeframe="1m", start_time=start)
        raw.pop(4)
        raw.append(dict(raw[2]))
        raw[-2]["close"] = 3000.0
        raw[-2]["high"] = 3000.0

        _candles, report = DataEngine().clean_candles(
            raw,
            instrument="XAUUSD",
            timeframe="1m",
            reference_time=start + timedelta(minutes=20),
            provider_status="AVAILABLE",
            max_freshness_seconds=120.0,
        )

        self.assertEqual(report.missing_candles, 1)
        self.assertEqual(report.duplicate_candles, 1)
        self.assertGreaterEqual(report.outlier_count, 1)
        self.assertGreaterEqual(report.out_of_order_count, 1)
        self.assertLess(report.quality_score, 85.0)
        self.assertTrue(any("stale" in reason.lower() for reason in report.blocking_reasons))

    def test_complete_aggregation_excludes_partial_buckets(self) -> None:
        raw = generate_synthetic_candles(
            count=7,
            timeframe="1m",
            start_time=datetime(2026, 1, 1, tzinfo=UTC),
        )
        candles, _report = DataEngine().clean_candles(raw, instrument="XAUUSD", timeframe="1m")

        all_buckets = DataEngine().aggregate_from_1m(candles, "5m")
        complete_buckets = DataEngine().aggregate_from_1m(candles, "5m", require_complete=True)

        self.assertEqual(len(all_buckets), 2)
        self.assertEqual(len(complete_buckets), 1)

    def test_enabled_gate_abstains_before_model_inference(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        raw = generate_synthetic_candles(count=80, timeframe="5m", start_time=start)
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            cycle_timeframe="5m",
            enable_data_quality_gate=True,
            enable_news_intelligence=False,
        )
        system = GoldSignalSystem(runtime=runtime)
        system.model_engine.run_models = Mock(side_effect=AssertionError("model inference must be skipped"))

        result = system.run_signal_cycle(
            raw,
            source_timeframe="5m",
            market_context=MarketContext(),
            data_reference_time=start + timedelta(days=2),
            provider_status="AVAILABLE",
        )

        self.assertEqual(result.data_quality_report.gate_status, "BLOCKED")
        self.assertEqual(result.recommendation.signal, SignalDirection.HOLD)
        self.assertTrue(
            any("Data quality gate" in reason for reason in result.recommendation.blocked_reasons)
        )
        self.assertTrue(all(vote.model_version == "DATA_QUALITY_ABSTAIN" for vote in result.recommendation.model_votes))
        self.assertIn("model_inference", result.processing_timings_ms)
        system.model_engine.run_models.assert_not_called()

    def test_gate_is_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {"ENABLE_DATA_QUALITY_GATE": ""}):
            runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)
        self.assertFalse(runtime.enable_data_quality_gate)

    def test_backtest_outcomes_include_spread_slippage_and_commission(self) -> None:
        engine = BacktestingEngine(
            system=Mock(),
            config=BacktestConfig(spread=0.20, slippage=0.10, commission_per_trade=0.05),
        )
        recommendation = SimpleNamespace(
            signal=SignalDirection.BUY,
            entry_price=100.0,
            stop_loss=99.0,
            take_profit_1=101.0,
            take_profit_2=102.0,
            take_profit_3=103.0,
        )

        outcome = engine._simulate_outcome(
            recommendation,
            [{"high": 101.0, "low": 100.0}],
        )

        self.assertEqual(outcome["outcome"], "TP1_HIT")
        self.assertAlmostEqual(float(outcome["gross_realized_rr"]), 1.0)
        self.assertAlmostEqual(float(outcome["trading_cost_rr"]), 0.45)
        self.assertAlmostEqual(float(outcome["realized_rr"]), 0.55)


if __name__ == "__main__":
    unittest.main()
