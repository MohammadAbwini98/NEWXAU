from __future__ import annotations

import os
import sys
import unittest

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.backtesting import BacktestingEngine
from datetime import UTC, datetime

from gold_signal_system.config import RuntimeConfig
from gold_signal_system.contracts import (
    AgreementStatus,
    EnsemblePrediction,
    IndicatorGroupScore,
    IndicatorSnapshot,
    MarketContext,
    RecommendationStatus,
    SignalDirection,
)
from gold_signal_system.live_control import LiveControlCenter
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.providers import CapitalComCandleProvider, build_candle_provider
from gold_signal_system.strategy_brain import StrategyBrain
from gold_signal_system.utils import generate_synthetic_candles


class GoldSignalSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system = GoldSignalSystem(runtime=RuntimeConfig(data_provider="synthetic", postgres_dsn=None))

    def test_phase1_clean_and_aggregate(self) -> None:
        candles = generate_synthetic_candles(count=240, timeframe="1m")
        result = self.system.run_signal_cycle(candles, source_timeframe="1m", market_context=MarketContext())

        self.assertGreaterEqual(result.data_quality_report.cleaned_rows, 200)
        self.assertIn("5m", result.aggregation_counts)
        self.assertIn("15m", result.aggregation_counts)
        self.assertIn("1h", result.aggregation_counts)

    def test_multi_timeframe_tops_up_native_4h_when_1m_history_is_capped(self) -> None:
        class Provider:
            def fetch_latest_candles(self, instrument: str, timeframe: str, limit: int) -> list[dict]:
                count = 900 if timeframe == "1m" else 40
                return generate_synthetic_candles(instrument=instrument, timeframe=timeframe, count=count)

        system = GoldSignalSystem(runtime=RuntimeConfig(data_provider="synthetic", postgres_dsn=None))
        system.candle_provider = Provider()

        result = system.run_live_cycle(source_timeframe="1m", market_context=MarketContext())
        summary = system.storage.latest_timeframe_confirmation()

        self.assertLess(result.aggregation_counts["4h"], 10)
        self.assertGreaterEqual(result.aggregation_counts["4h_native"], 10)
        self.assertNotEqual(summary.get("timeframes", {}).get("4h", {}).get("bias"), "INSUFFICIENT_DATA")

    def test_end_to_end_recommendation_shape(self) -> None:
        candles = generate_synthetic_candles(count=900, timeframe="1m")
        result = self.system.run_signal_cycle(candles, source_timeframe="1m", market_context=MarketContext())
        rec = result.recommendation

        self.assertEqual(rec.instrument, "XAUUSD")
        self.assertIn(
            rec.status,
            {
                RecommendationStatus.RECOMMENDED,
                RecommendationStatus.WEAK_RECOMMENDATION,
                RecommendationStatus.HOLD,
                RecommendationStatus.BLOCKED_BY_LOW_CONFIDENCE,
                RecommendationStatus.BLOCKED_BY_MODEL_CONFLICT,
                RecommendationStatus.BLOCKED_BY_RISK,
                RecommendationStatus.BLOCKED_BY_SPREAD,
                RecommendationStatus.BLOCKED_BY_NEWS,
                RecommendationStatus.BLOCKED_BY_LOW_RR,
                RecommendationStatus.BLOCKED_BY_BAD_ENTRY,
                RecommendationStatus.BLOCKED_BY_MARKET_STRUCTURE,
            },
        )
        self.assertTrue(len(rec.model_votes) >= 3)
        self.assertIn("trend", rec.indicator_summary)
        if rec.signal != SignalDirection.HOLD:
            self.assertIsNotNone(rec.entry_price)
            self.assertIsNotNone(rec.stop_loss)
            self.assertIsNotNone(rec.take_profit_1)
            self.assertIsNotNone(rec.take_profit_2)
            self.assertIsNotNone(rec.take_profit_3)
            if rec.signal == SignalDirection.BUY:
                self.assertLess(rec.stop_loss, rec.entry_price)
                self.assertLess(rec.entry_price, rec.take_profit_1)
                self.assertLess(rec.take_profit_1, rec.take_profit_2)
                self.assertLess(rec.take_profit_2, rec.take_profit_3)
            if rec.signal == SignalDirection.SELL:
                self.assertGreater(rec.stop_loss, rec.entry_price)
                self.assertGreater(rec.entry_price, rec.take_profit_1)
                self.assertGreater(rec.take_profit_1, rec.take_profit_2)
                self.assertGreater(rec.take_profit_2, rec.take_profit_3)
            self.assertIsNotNone(rec.risk_amount)
            self.assertIsNotNone(rec.risk_reward)
            self.assertIn(rec.risk_level, {"LOW", "MEDIUM", "HIGH", "BLOCKED"})
            self.assertIn(rec.outcome_status, {"PENDING", "WAITING_FOR_ENTRY", "ENTRY_TRIGGERED"})

    def test_all_active_model_artifacts_are_loaded(self) -> None:
        statuses = self.system.model_engine.artifact_status
        expected = {"kronos", "tcn", "lightgbm", "patchtst", "cnn_lstm", "nhits"}

        self.assertEqual(set(statuses), expected)
        for model_name in expected:
            self.assertEqual(statuses[model_name]["status"], "LOADED")

        # LightGBM is served by a trained joblib artifact; the sequence models
        # (and kronos) use python adapters that load their own weights.
        self.assertEqual(statuses["lightgbm"]["kind"], "joblib")
        for model_name in ("kronos", "tcn", "patchtst", "cnn_lstm", "nhits"):
            self.assertEqual(statuses[model_name]["kind"], "python")

    def test_backtest_engine_runs(self) -> None:
        candles = generate_synthetic_candles(count=1100, timeframe="1m")
        report = BacktestingEngine(self.system).run(candles)
        self.assertIn("win_rate", report)
        self.assertIn("profit_factor", report)

    def test_live_control_emergency_stop(self) -> None:
        candles = generate_synthetic_candles(count=900, timeframe="1m")
        rec = self.system.run_signal_cycle(candles).recommendation
        control = LiveControlCenter()
        control.enable_emergency_stop()
        status = control.process_recommendation(rec, confirmed=True)
        self.assertEqual(status, "BLOCKED: Emergency stop enabled")

    def test_storage_history_and_detail_reads(self) -> None:
        candles = generate_synthetic_candles(count=900, timeframe="1m")
        self.system.run_signal_cycle(candles, source_timeframe="1m", market_context=MarketContext())

        history = self.system.storage.get_signal_history(page=1, page_size=10)
        self.assertGreaterEqual(history["total"], 1)
        self.assertGreaterEqual(len(history["items"]), 1)

        detail = self.system.storage.get_signal_detail(1)
        self.assertIsNotNone(detail)
        self.assertIn("instrument", detail)

    def test_dynamic_weight_adaptation_updates_weights(self) -> None:
        candles = generate_synthetic_candles(count=900, timeframe="1m")
        result = self.system.run_signal_cycle(candles, source_timeframe="1m", market_context=MarketContext())

        initial = dict(self.system.model_engine.model_weights.weights)
        for _ in range(12):
            self.system.record_model_outcome(
                recommendation=result.recommendation,
                realized_rr=1.5,
                outcome="TP2_HIT",
                source="backtest",
            )

        updated = dict(self.system.model_engine.model_weights.weights)
        self.assertNotEqual(initial, updated)
        self.assertAlmostEqual(sum(updated.values()), 1.0, places=6)

    def test_strategy_penalizes_direction_mismatched_indicators(self) -> None:
        now = datetime.now(tz=UTC)
        ensemble = EnsemblePrediction(
            instrument="XAUUSD",
            timeframe="5m",
            prediction_time=now,
            ensemble_signal=SignalDirection.SELL,
            ensemble_confidence=0.82,
            buy_score=0.08,
            sell_score=0.82,
            hold_score=0.10,
            agreement_status=AgreementStatus.STRONG,
            active_models=["KRONOS", "TCN", "LightGBM"],
            conflicting_models=[],
            summary="Strong sell test fixture.",
        )
        snapshot = IndicatorSnapshot(
            instrument="XAUUSD",
            timeframe="5m",
            snapshot_time=now,
            trend=IndicatorGroupScore(bias="BULLISH", score=85),
            momentum=IndicatorGroupScore(bias="POSITIVE", score=80),
            volatility_status="VALID",
            atr=1.2,
            nearest_support=2340.0,
            nearest_resistance=2360.0,
            structure_bias="BULLISH_HH_HL",
            session_name="LONDON",
            news_status="CLEAR",
            raw_json={},
        )

        decision = StrategyBrain().evaluate(ensemble, snapshot, entry_quality_score=90, risk_passed=True)

        self.assertEqual(decision.signal, SignalDirection.SELL)
        # Indicator misconfirmation is now a score penalty, not a hard veto: the
        # contradicted setup is penalized below the actionable threshold (-> HOLD)
        # rather than blocked outright, so it never reaches RECOMMENDED/WEAK.
        self.assertNotIn(
            decision.status,
            {RecommendationStatus.RECOMMENDED, RecommendationStatus.WEAK_RECOMMENDATION},
        )
        self.assertEqual(decision.status, RecommendationStatus.HOLD)
        self.assertIn("Trend does not confirm model direction (score penalty applied).", decision.reasons)
        self.assertIn("Momentum does not confirm model direction (score penalty applied).", decision.reasons)
        self.assertIn("Market structure does not confirm model direction (score penalty applied).", decision.reasons)

    def test_capitalcom_provider_maps_existing_project_config_style(self) -> None:
        provider = build_candle_provider(
            RuntimeConfig(
                data_provider="capitalcom",
                capitalcom_api_base="https://demo-api-capital.backend-capital.com/api/v1",
                capitalcom_api_key="test-key",
                capitalcom_identifier="test-user",
                capitalcom_password="test-password",
                capitalcom_epic="GOLD",
                capitalcom_price_side="mid",
                capitalcom_use_encrypted_password=False,
            )
        )

        self.assertIsInstance(provider, CapitalComCandleProvider)
        self.assertEqual(provider._build_url("/session"), "https://demo-api-capital.backend-capital.com/api/v1/session")
        self.assertEqual(provider._build_url("/prices/GOLD"), "https://demo-api-capital.backend-capital.com/api/v1/prices/GOLD")
        self.assertEqual(provider._timeframe_to_resolution("4h"), "HOUR_4")

    def test_capitalcom_provider_fetches_and_maps_candles(self) -> None:
        class FakeResponse:
            def __init__(self, payload, headers=None) -> None:
                self._payload = payload
                self.headers = headers or {}
                self.status_code = 200

            def raise_for_status(self) -> None:
                return None

            def json(self):
                return self._payload

        class FakeSession:
            def __init__(self) -> None:
                self.headers = {}
                self.auth_payload = None
                self.price_params = None

            def post(self, url, json, timeout):
                self.auth_payload = json
                return FakeResponse({}, {"CST": "cst", "X-SECURITY-TOKEN": "token"})

            def get(self, url, params, timeout):
                self.price_params = params
                return FakeResponse(
                    {
                        "prices": [
                            {
                                "snapshotTimeUTC": "2026-06-07T10:00:00Z",
                                "openPrice": {"bid": 2350.0, "ask": 2350.2},
                                "highPrice": {"bid": 2351.0, "ask": 2351.2},
                                "lowPrice": {"bid": 2349.0, "ask": 2349.2},
                                "closePrice": {"bid": 2350.5, "ask": 2350.7},
                                "lastTradedVolume": 12,
                            }
                        ]
                    }
                )

        provider = CapitalComCandleProvider(
            api_base="https://demo-api-capital.backend-capital.com/api/v1",
            api_key="test-key",
            identifier="test-user",
            password="test-password",
            epic="GOLD",
            price_side="mid",
            use_encrypted_password=False,
        )
        fake_session = FakeSession()
        provider._session = fake_session

        rows = provider.fetch_latest_candles("XAUUSD", "1m", 10)

        self.assertEqual(fake_session.auth_payload["encryptedPassword"], False)
        self.assertEqual(fake_session.price_params["resolution"], "MINUTE")
        self.assertEqual(rows[0]["candle_time"], "2026-06-07T10:00:00Z")
        self.assertAlmostEqual(rows[0]["open"], 2350.1)
        self.assertAlmostEqual(rows[0]["close"], 2350.6)

    def test_capitalcom_provider_reauthenticates_once_after_401(self) -> None:
        price_payload = {
            "prices": [
                {
                    "snapshotTimeUTC": "2026-07-15T14:45:00Z",
                    "openPrice": {"bid": 4058.0, "ask": 4058.2},
                    "highPrice": {"bid": 4059.0, "ask": 4059.2},
                    "lowPrice": {"bid": 4057.0, "ask": 4057.2},
                    "closePrice": {"bid": 4058.5, "ask": 4058.7},
                    "lastTradedVolume": 8,
                }
            ]
        }

        class FakeResponse:
            def __init__(self, status_code, payload=None, headers=None) -> None:
                self.status_code = status_code
                self._payload = payload or {}
                self.headers = headers or {}

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise requests.HTTPError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeSession:
            def __init__(self) -> None:
                self.headers = {}
                self.post_calls = 0
                self.get_calls = 0
                self.request_tokens = []

            def post(self, url, json, timeout):
                self.post_calls += 1
                return FakeResponse(
                    200,
                    headers={
                        "CST": f"cst-{self.post_calls}",
                        "X-SECURITY-TOKEN": f"token-{self.post_calls}",
                    },
                )

            def get(self, url, params, timeout):
                self.get_calls += 1
                self.request_tokens.append(
                    (self.headers.get("CST"), self.headers.get("X-SECURITY-TOKEN"))
                )
                if self.get_calls == 1:
                    return FakeResponse(401)
                return FakeResponse(200, payload=price_payload)

        provider = CapitalComCandleProvider(
            api_base="https://demo-api-capital.backend-capital.com/api/v1",
            api_key="test-key",
            identifier="test-user",
            password="test-password",
            epic="GOLD",
        )
        fake_session = FakeSession()
        provider._session = fake_session

        rows = provider.fetch_latest_candles("XAUUSD", "1m", 10)

        self.assertEqual(fake_session.post_calls, 2)
        self.assertEqual(fake_session.get_calls, 2)
        self.assertEqual(
            fake_session.request_tokens,
            [("cst-1", "token-1"), ("cst-2", "token-2")],
        )
        self.assertEqual(rows[0]["candle_time"], "2026-07-15T14:45:00Z")

    def test_capitalcom_provider_rejects_auth_without_both_tokens(self) -> None:
        class FakeResponse:
            status_code = 200
            headers = {"CST": "cst-only"}

            def raise_for_status(self) -> None:
                return None

        class FakeSession:
            def __init__(self) -> None:
                self.headers = {}

            def post(self, url, json, timeout):
                return FakeResponse()

            def get(self, url, params, timeout):
                raise AssertionError("Price request must not run without both auth tokens.")

        provider = CapitalComCandleProvider(
            api_base="https://demo-api-capital.backend-capital.com/api/v1",
            api_key="test-key",
            identifier="test-user",
            password="test-password",
            epic="GOLD",
        )
        provider._session = FakeSession()

        with self.assertRaisesRegex(RuntimeError, "CST/X-SECURITY-TOKEN"):
            provider.fetch_latest_candles("XAUUSD", "1m", 10)

        self.assertFalse(provider._authenticated)


if __name__ == "__main__":
    unittest.main()
