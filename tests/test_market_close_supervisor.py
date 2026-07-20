from __future__ import annotations

from datetime import UTC, datetime
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system import api
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.market_hours import market_hours_state


class MarketCloseSupervisorTests(unittest.TestCase):
    def test_gold_market_default_window_is_closed_after_friday_close(self) -> None:
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)

        state = market_hours_state(runtime, datetime(2026, 6, 12, 22, 0, tzinfo=UTC))

        self.assertFalse(state.is_open)
        self.assertEqual(state.closure_key, "20260612T210000Z")

    def test_gold_market_default_window_is_open_before_friday_close(self) -> None:
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)

        state = market_hours_state(runtime, datetime(2026, 6, 12, 20, 59, tzinfo=UTC))

        self.assertTrue(state.is_open)
        self.assertIsNone(state.closure_key)

    def test_daily_broker_break_pauses_market_before_weekly_close(self) -> None:
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None, market_daily_break_enabled=True)

        state = market_hours_state(runtime, datetime(2026, 6, 11, 21, 45, tzinfo=UTC))

        self.assertFalse(state.is_open)
        self.assertEqual(state.closure_key, "20260611T210000Z")
        self.assertEqual(state.next_transition.isoformat(), "2026-06-11T22:00:00+00:00")

    def test_market_close_backtest_payload_is_deterministic(self) -> None:
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)
        old_runtime = api.runtime
        try:
            api.runtime = runtime
            state = market_hours_state(runtime, datetime(2026, 6, 12, 22, 0, tzinfo=UTC))
            payload = api._market_close_backtest_payload("AUTO_MARKET_CLOSE_20260612T210000Z", state)

            self.assertEqual(payload["run_type"], "WALK_FORWARD")
            self.assertEqual(payload["run_id"], "AUTO_MARKET_CLOSE_20260612T210000Z")
            self.assertEqual(payload["source"], "market_close_supervisor")
            self.assertEqual(payload["market_close"]["closure_key"], "20260612T210000Z")
        finally:
            api.runtime = old_runtime


if __name__ == "__main__":
    unittest.main()
