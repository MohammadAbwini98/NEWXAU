from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

os.environ["POSTGRES_DSN"] = ""
os.environ["DATA_PROVIDER"] = "synthetic"
os.environ["ENABLE_BACKGROUND_CYCLE_RUNNER"] = "0"
os.environ["ENABLE_LIVE_PRICE_STREAM"] = "0"
os.environ["NEWS_COLLECTION_ENABLED"] = "0"
os.environ["NEWS_AI_ANALYSIS_ENABLED"] = "0"

from gold_signal_system import api
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.pipeline import GoldSignalSystem


class DashboardStartupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            instrument="XAUUSD",
            capitalcom_epic="XAUUSD",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            live_candle_lookback=300,
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.latest_price_tick = None
        api.latest_price_stream_status = {"status": "WAITING_FOR_STREAM"}
        api.background_cycle_status = {
            "status": "WAITING_TO_START",
            "last_started_at": None,
            "last_success_at": None,
            "last_error_at": None,
            "last_error": None,
            "last_signal_time": None,
            "last_session": None,
            "consecutive_errors": 0,
        }

    def tearDown(self) -> None:
        if hasattr(api.system.storage, "close"):
            api.system.storage.close()

    def test_dashboard_route_is_project_entrypoint(self) -> None:
        response = api.dashboard()

        self.assertTrue(str(response.path).endswith("src/gold_signal_system/dashboard_static/index.html"))

    def test_sidebar_items_are_actionable_buttons(self) -> None:
        dashboard_path = os.path.join(ROOT, "src", "gold_signal_system", "dashboard_static", "index.html")
        with open(dashboard_path, encoding="utf-8") as handle:
            html = handle.read()

        for view in (
            "dashboard",
            "live",
            "control",
            "history",
            "models",
            "indicators",
            "risk",
            "backtesting",
            "paper",
            "settings",
            "logs",
        ):
            self.assertIn(f'button class="nav-item', html)
            self.assertIn(f'data-view="{view}"', html)

        self.assertIn("setActiveView", html)
        self.assertIn('id="live-price"', html)
        self.assertIn('id="live-price-time"', html)
        self.assertIn('payload.event === "price.tick"', html)
        self.assertIn("/api/execution/control", html)
        self.assertIn("/api/execution/control/stats", html)

    def test_dashboard_renders_market_session_schedule_and_active_state(self) -> None:
        dashboard_path = os.path.join(ROOT, "src", "gold_signal_system", "dashboard_static", "index.html")
        with open(dashboard_path, encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn("function renderMarketSessions()", html)
        self.assertIn("control.session_config", html)
        self.assertIn('class="market-session${isActive ? " active" : ""}', html)
        self.assertIn('aria-current="${isActive ? "true" : "false"}"', html)
        self.assertIn("Active now", html)
        self.assertIn("Asia/Amman", html)

    async def test_latest_price_endpoint_reports_stream_state(self) -> None:
        price = await api.get_latest_price()

        self.assertEqual(price["status"], "DISABLED")
        self.assertEqual(price["instrument"], "XAUUSD")
        self.assertEqual(price["source"], "capital.com.websocket")

    async def test_dashboard_summary_seeds_full_signal_stack(self) -> None:
        self.assertIsNone(api.system.storage.latest_recommendation())

        summary = await api.get_dashboard_summary()

        latest = api.system.storage.latest_recommendation()
        self.assertIsNotNone(latest)
        self.assertIsNotNone(summary["current_signal"])
        self.assertGreaterEqual(len(api.system.storage.latest_model_votes()), 6)
        self.assertIsNotNone(api.system.storage.latest_indicator_snapshot())
        self.assertGreaterEqual(len(api.system.storage.strategy_decisions), 1)
        self.assertGreaterEqual(len(api.system.storage.trade_recommendations), 1)

    async def test_dashboard_api_exposes_model_votes_indicators_and_risk(self) -> None:
        await api.get_dashboard_summary()

        votes = await api.get_latest_model_votes()
        indicators = await api.get_latest_indicators()
        risk = await api.get_risk_status()
        outcomes = await api.get_signal_outcomes()

        self.assertGreaterEqual(len(votes), 6)
        self.assertIn("trend", indicators)
        self.assertIn("risk_status", risk)
        self.assertIn("items", outcomes)

    async def test_signal_snapshot_and_recent_signal_endpoints(self) -> None:
        await api.get_dashboard_summary()

        recent = await api.get_recent_signals()
        self.assertGreaterEqual(recent["total"], 1)
        signal_id = recent["items"][0]["id"]

        snapshot = await api.get_signal_snapshot(signal_id)
        outcome = await api.get_signal_outcome(signal_id)

        self.assertEqual(snapshot["signal_id"], signal_id)
        self.assertIn("model_votes_json", snapshot)
        self.assertIn("model_weights_json", snapshot)
        self.assertIn("raw_recommendation_json", snapshot)
        self.assertEqual(outcome["recommendation_id"], signal_id)
        self.assertIn(outcome["outcome"], {"PENDING", "WIN", "LOSS", "PARTIAL_TP", "BREAKEVEN", "EXPIRED", "MISSED_ENTRY", "NO_TRADE"})

    async def test_improvement_roadmap_api_endpoints_are_wired(self) -> None:
        await api.get_dashboard_summary()
        recent = await api.get_recent_signals()
        signal_id = recent["items"][0]["id"]

        self.assertIn("primary_regime", await api.get_current_market_regime())
        self.assertIn("status", await api.get_current_timeframe_confirmation())
        self.assertIn("status", await api.get_current_news_risk())
        self.assertIn("overall_status", await api.get_system_health())
        self.assertIn("details", await api.get_current_model_weights())
        self.assertIn("model_signal_predictions", await api.get_model_performance_summary())
        self.assertIn("items", await api.get_signal_entry_plans(signal_id))
        self.assertIn("signal", await api.get_signal_replay(signal_id))

    async def test_system_health_exposes_background_cycle_state(self) -> None:
        health = await api.get_system_health()

        self.assertIn("background_cycle", health)
        self.assertEqual(health["background_cycle"]["status"], "DISABLED")
        self.assertTrue(health["background_cycle"]["healthy"])
        self.assertEqual(health["categories"]["background_cycle"], "HEALTHY")

    def test_background_cycle_errors_are_persisted_to_health_events(self) -> None:
        details = api._record_background_cycle_error(RuntimeError("cycle stalled in test"))
        events = api.system.storage.get_health_events()

        self.assertEqual(details["status"], "ERROR")
        self.assertEqual(details["consecutive_errors"], 1)
        self.assertGreaterEqual(events["total"], 1)
        self.assertIn("cycle stalled in test", events["items"][0]["message"])


if __name__ == "__main__":
    unittest.main()
