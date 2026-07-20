from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.contracts import Candle, IndicatorGroupScore, IndicatorSnapshot, ModelPrediction, SignalDirection
from gold_signal_system.dynamic_weights import DynamicModelWeightService
from gold_signal_system.health import SystemHealthService
from gold_signal_system.market_regime import MarketRegimeDetector
from gold_signal_system.multi_timeframe import MultiTimeframeConfirmationService
from gold_signal_system.news_filter import EconomicNewsEvent, EconomicNewsFilter, ManualEconomicCalendarProvider
from gold_signal_system.optimization import ThresholdOptimizationService
from gold_signal_system.trade_plan_engine import EntrySlTpEngine
from gold_signal_system.walk_forward import WalkForwardBacktestService, WalkForwardConfig


def _candles(count: int = 40, start: float = 100.0, step: float = 0.2, timeframe: str = "5m") -> list[Candle]:
    base = datetime(2026, 6, 8, 8, 0, tzinfo=UTC)
    minutes = 1 if timeframe == "1m" else 5 if timeframe == "5m" else 15 if timeframe == "15m" else 60
    rows = []
    for idx in range(count):
        close = start + idx * step
        rows.append(
            Candle(
                instrument="XAUUSD",
                timeframe=timeframe,
                candle_time=base + timedelta(minutes=minutes * idx),
                open=close - step / 2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
            )
        )
    return rows


def _snapshot() -> IndicatorSnapshot:
    return IndicatorSnapshot(
        instrument="XAUUSD",
        timeframe="5m",
        snapshot_time=datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
        trend=IndicatorGroupScore(bias="BULLISH", score=82),
        momentum=IndicatorGroupScore(bias="POSITIVE", score=75),
        volatility_status="VALID",
        atr=1.2,
        nearest_support=101.0,
        nearest_resistance=112.0,
        structure_bias="BULLISH_HH_HL",
        session_name="LONDON",
        news_status="CLEAR",
        raw_json={"ema20": 107.0, "ema50": 104.0, "ema200": 100.0, "adx": 25},
    )


def _prediction(model: str, signal: SignalDirection = SignalDirection.BUY, confidence: float = 0.8) -> ModelPrediction:
    return ModelPrediction(
        model_name=model,
        model_version="v1",
        instrument="XAUUSD",
        timeframe="5m",
        prediction_time=datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
        signal=signal,
        buy_probability=confidence if signal == SignalDirection.BUY else 0.1,
        sell_probability=confidence if signal == SignalDirection.SELL else 0.1,
        hold_probability=confidence if signal == SignalDirection.HOLD else 0.1,
        confidence=confidence,
        expected_return=0.002,
        expected_range=2.0,
        prediction_horizon_candles=6,
    )


class ImprovementServiceTests(unittest.TestCase):
    def test_market_regime_detects_uptrend(self) -> None:
        regime = MarketRegimeDetector().detect(_snapshot(), _candles())
        self.assertEqual(regime.primary_regime, "TRENDING_UP")

    def test_dynamic_weight_increases_strong_model_and_decreases_failed_health(self) -> None:
        service = DynamicModelWeightService()
        results = service.calculate(
            {"kronos": 0.5, "tcn": 0.5},
            [_prediction("kronos"), _prediction("tcn")],
            {"kronos": {"observations": 10, "win_rate": 0.7, "buy_precision": 0.7}, "tcn": {"observations": 10, "win_rate": 0.3, "buy_precision": 0.3}},
            market_regime="TRENDING_UP",
            session="LONDON",
        )
        weights = {item.model_name: item.effective_weight for item in results}
        self.assertGreater(weights["kronos"], weights["tcn"])

        failed = service.calculate({"kronos": 0.5}, [_prediction("kronos")], {}, health_by_model={"kronos": "FAILED"})
        self.assertEqual(failed[0].effective_weight, 0.0)

    def test_dynamic_weights_retain_configured_baseline_until_enough_observations(self) -> None:
        service = DynamicModelWeightService(min_observations_for_reweight=10)
        service._last_effective_weights = {"kronos": 0.01, "tcn": 0.99}

        results = service.calculate(
            {"kronos": 0.30, "tcn": 0.25},
            [_prediction("kronos"), _prediction("tcn")],
            {"kronos": {"observations": 2}, "tcn": {"observations": 2}},
            market_regime="TRENDING_UP",
            session="LONDON",
        )

        weights = {item.model_name: item.effective_weight for item in results}
        reasons = {item.model_name: item.adjustment_reason for item in results}
        self.assertAlmostEqual(weights["kronos"], 0.30 / 0.55, places=6)
        self.assertAlmostEqual(weights["tcn"], 0.25 / 0.55, places=6)
        self.assertTrue(reasons["kronos"]["baseline_retained"])
        self.assertEqual(reasons["kronos"]["required_observations"], 10)

    def test_news_filter_blocks_high_impact_usd_event(self) -> None:
        provider = ManualEconomicCalendarProvider()
        now = datetime(2026, 6, 8, 10, 0, tzinfo=UTC)
        provider.add_event(EconomicNewsEvent("manual", "US CPI YoY", "US", "USD", "HIGH", now + timedelta(minutes=18)))
        risk = EconomicNewsFilter(provider).current_risk(now)
        self.assertEqual(risk.status, "BLOCKED")

    def test_multi_timeframe_buy_alignment(self) -> None:
        service = MultiTimeframeConfirmationService()
        candles_by_tf = {tf: _candles(timeframe=tf) for tf in ("1m", "5m", "15m", "1h", "4h")}
        result = service.evaluate(SignalDirection.BUY, candles_by_tf)
        self.assertIn(result.status, {"ALIGNED", "MIXED"})
        self.assertGreater(result.alignment_score, 50)

    def test_entry_plan_scoring_selects_valid_plan(self) -> None:
        plans = EntrySlTpEngine().generate_candidate_plans(SignalDirection.BUY, _snapshot(), 108.0, 0.8, "TRENDING_UP")
        selected = [plan for plan in plans if plan.selected]
        self.assertEqual(len(selected), 1)
        self.assertGreaterEqual(selected[0].final_plan_score, 0)

    def test_health_reports_missing_candle_critical(self) -> None:
        health = SystemHealthService().check([], "5m")
        self.assertEqual(health["overall_status"], "CRITICAL")

    def test_walk_forward_windows_generated(self) -> None:
        candles = [{"candle_time": str(idx), "open": 1, "high": 2, "low": 0, "close": 1, "volume": 0} for idx in range(30)]
        service = WalkForwardBacktestService(system=None)
        windows = service.generate_windows(candles, WalkForwardConfig(train_size=10, test_size=5, step_size=5))
        self.assertEqual(len(windows), 4)

    def test_optimizer_penalizes_low_trade_count(self) -> None:
        service = ThresholdOptimizationService(walk_forward_service=None)
        score, rejected = service.score_candidate({"total_signals": 1, "win_rate": 0.9, "profit_factor": 3, "max_drawdown": 0, "average_rr": 2})
        self.assertEqual(rejected, "Low trade count.")
        self.assertLess(score, 100)


if __name__ == "__main__":
    unittest.main()
