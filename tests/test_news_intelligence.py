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
from gold_signal_system.news_intelligence.ai_analyzer import AiNewsAnalyzer
from gold_signal_system.news_intelligence.collectors import (
    classify_relevance,
    generate_news_hash,
    normalize_news_payload,
)
from gold_signal_system.news_intelligence.macro_events import calculate_risk_window, current_risk_window
from gold_signal_system.news_intelligence.models import MacroEventModel, NewsRelevance, StrategyNewsStateModel
from gold_signal_system.news_intelligence.repository import NewsIntelligenceRepository
from gold_signal_system.news_intelligence.service import NewsIntelligenceService
from gold_signal_system.news_intelligence.strategy_integration import NewsStateAggregator
from gold_signal_system.pipeline import GoldSignalSystem


class NewsIntelligenceCoreTests(unittest.TestCase):
    def test_news_hash_is_stable_and_timestamp_sensitive(self) -> None:
        published = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
        first = generate_news_hash(" Gold rallies after CPI ", "Reuters", "XAUUSD", published)
        second = generate_news_hash("gold rallies after cpi", "reuters", "xauusd", published)
        other = generate_news_hash("gold rallies after cpi", "reuters", "xauusd", published + timedelta(minutes=1))

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_relevance_classifier_prioritizes_xauusd_terms(self) -> None:
        self.assertEqual(classify_relevance("Gold jumps as Fed hints at cuts").value, NewsRelevance.HIGH.value)
        self.assertEqual(classify_relevance("Ethereum protocol upgrade announced").value, NewsRelevance.LOW.value)
        self.assertEqual(classify_relevance("Treasury yields rise before auction").value, NewsRelevance.MEDIUM.value)

    def test_ai_json_validation_clamps_weight_and_accepts_required_schema(self) -> None:
        analyzer = AiNewsAnalyzer(RuntimeConfig(data_provider="synthetic", postgres_dsn=None, news_max_weight_normal=0.2))
        parsed = analyzer.parse_and_validate_response(
            """
            {
              "instrument": "XAUUSD",
              "news_relevance": "HIGH",
              "direction": "UP",
              "trade_bias": "BUY",
              "confidence": 1.4,
              "impact_strength": "HIGH",
              "expected_time_window": "1-4 hours",
              "market_session": "New York",
              "volatility_expected": "HIGH",
              "risk_level": "HIGH",
              "action_level": "WEIGHT_ONLY",
              "should_block_trading": false,
              "should_reduce_position_size": false,
              "summary": "Gold positive.",
              "reasoning_points": ["USD lower"],
              "recommended_strategy_action": {
                "news_weight": 0.9,
                "max_position_multiplier": 2.0,
                "valid_until_minutes": 240
              }
            }
            """,
            event_type="GENERAL_GOLD_NEWS",
        )

        self.assertEqual(parsed.confidence, 1.0)
        self.assertLessEqual(parsed.recommended_strategy_action.news_weight, 0.2)
        self.assertLessEqual(parsed.recommended_strategy_action.max_position_multiplier, 1.05)

    def test_macro_risk_window_marks_active_event(self) -> None:
        scheduled = datetime.now(tz=UTC) + timedelta(minutes=10)
        event = {
            "event_type": "CPI",
            "title": "US CPI",
            "scheduled_at": scheduled.isoformat(),
            "importance": "HIGH",
        }
        window = calculate_risk_window("CPI", scheduled)
        risk = current_risk_window([event], now=datetime.now(tz=UTC))

        self.assertEqual(window["block_before_minutes"], 30)
        self.assertEqual(risk["status"], "ACTIVE")

    def test_aggregator_conflicting_news_reduces_risk_without_forcing_direction(self) -> None:
        repo = NewsIntelligenceRepository()
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)
        analyzer = AiNewsAnalyzer(runtime)
        now = datetime.now(tz=UTC)
        up = normalize_news_payload(
            {"title": "Gold rises on safe haven war escalation", "source": "manual", "published_at": now.isoformat()},
            "XAUUSD",
        )
        down = normalize_news_payload(
            {"title": "Hot CPI sends yields and dollar higher", "source": "manual", "published_at": now.isoformat()},
            "XAUUSD",
        )
        up_id = repo.save_news_item(up, generate_news_hash(up.title, up.source, up.instrument, up.published_at))
        down_id = repo.save_news_item(down, generate_news_hash(down.title, down.source, down.instrument, down.published_at))
        repo.save_ai_analysis(analyzer.analyze_news_item(up), news_item_id=up_id)
        repo.save_ai_analysis(analyzer.analyze_news_item(down), news_item_id=down_id)

        state = NewsStateAggregator(repo, runtime).aggregate("XAUUSD")

        self.assertEqual(state.active_direction, "MIXED")
        self.assertEqual(state.active_trade_bias, "NO_TRADE")
        self.assertTrue(state.reduce_position_size)

    def test_pipeline_rollout_flags_disable_live_weight_and_blocking(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            news_strategy_weight_enabled=False,
            news_trade_block_enabled=False,
        )
        system = GoldSignalSystem(runtime=runtime)
        state = StrategyNewsStateModel(
            id=7,
            instrument="XAUUSD",
            active_direction="UP",
            active_trade_bias="BUY",
            active_confidence=0.9,
            active_news_weight=0.35,
            block_trading=True,
            reduce_position_size=True,
            action_level="BLOCK_NEW_TRADES",
            reason="test",
            active_event_type="CPI",
            valid_until=datetime.now(tz=UTC) + timedelta(hours=1),
        )

        strategy_state = system._news_state_for_strategy(state)
        risk_state = system._news_state_for_risk(state)

        self.assertEqual(strategy_state.active_news_weight, 0.0)
        self.assertIsNone(risk_state)


class NewsIntelligenceApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            news_ai_analysis_enabled=True,
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)

    async def test_manual_news_endpoint_stores_and_analyzes_item(self) -> None:
        result = await api.create_manual_news(
            {
                "instrument": "XAUUSD",
                "source": "manual_test",
                "title": "Gold rises as Treasury yields fall",
                "published_at": datetime.now(tz=UTC).isoformat(),
            }
        )
        items = await api.get_news_items(instrument="XAUUSD", limit=10)
        analysis = await api.get_news_analysis(instrument="XAUUSD", limit=10)

        self.assertIsNotNone(result["id"])
        self.assertGreaterEqual(len(items["items"]), 1)
        self.assertGreaterEqual(len(analysis["items"]), 1)

    async def test_manual_macro_event_and_risk_window_endpoint(self) -> None:
        scheduled = datetime.now(tz=UTC) + timedelta(minutes=10)
        result = await api.create_manual_macro_event(
            {
                "event_type": "CPI",
                "title": "US CPI YoY",
                "country": "US",
                "currency": "USD",
                "scheduled_at": scheduled.isoformat(),
                "importance": "HIGH",
                "forecast_value": "3.1%",
                "previous_value": "3.0%",
            }
        )
        risk = await api.get_news_risk_window("XAUUSD")

        self.assertIsNotNone(result["id"])
        self.assertEqual(risk["status"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
