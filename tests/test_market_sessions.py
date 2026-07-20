from __future__ import annotations

from datetime import UTC, datetime
import os
import sys
import unittest
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.contracts import ExecutionControlConfig, normalize_execution_session_name
from gold_signal_system.market_sessions import get_gold_market_session, resolve_gold_market_session


JORDAN = ZoneInfo("Asia/Amman")


class GoldMarketSessionTests(unittest.TestCase):
    def test_jordan_local_boundaries(self) -> None:
        cases = [
            ("2026-06-30T00:00:00+03:00", "DAILY_BREAK"),
            ("2026-06-30T00:30:00+03:00", "DAILY_BREAK"),
            ("2026-06-30T00:59:00+03:00", "DAILY_BREAK"),
            ("2026-06-30T01:00:00+03:00", "ASIA_LOW"),
            ("2026-06-30T03:00:00+03:00", "ASIA_LOW"),
            ("2026-06-30T09:59:00+03:00", "ASIA_LOW"),
            ("2026-06-30T10:00:00+03:00", "LONDON_ACTIVE"),
            ("2026-06-30T15:59:00+03:00", "LONDON_ACTIVE"),
            ("2026-06-30T16:00:00+03:00", "US_OVERLAP"),
            ("2026-06-30T18:59:00+03:00", "US_OVERLAP"),
            ("2026-06-30T19:00:00+03:00", "NY_ACTIVE"),
            ("2026-06-30T23:59:00+03:00", "NY_ACTIVE"),
            ("2026-07-01T00:00:00+03:00", "DAILY_BREAK"),
        ]

        for raw_time, expected in cases:
            with self.subTest(raw_time=raw_time):
                self.assertEqual(get_gold_market_session(datetime.fromisoformat(raw_time)), expected)

    def test_utc_inputs_convert_to_jordan_time_before_classification(self) -> None:
        overlap = resolve_gold_market_session(datetime(2026, 6, 30, 13, 0, tzinfo=UTC))
        daily_break = resolve_gold_market_session(datetime(2026, 6, 30, 21, 30, tzinfo=UTC))

        self.assertEqual(overlap.jordan_time.astimezone(JORDAN).hour, 16)
        self.assertEqual(overlap.session, "US_OVERLAP")
        self.assertEqual(daily_break.jordan_time.date().isoformat(), "2026-07-01")
        self.assertEqual(daily_break.jordan_time.hour, 0)
        self.assertEqual(daily_break.session, "DAILY_BREAK")
        self.assertFalse(daily_break.trading_allowed)

    def test_legacy_control_unit_session_names_normalize_to_gold_sessions(self) -> None:
        self.assertEqual(normalize_execution_session_name("ASIAN"), "ASIA_LOW")
        self.assertEqual(normalize_execution_session_name("LONDON"), "LONDON_ACTIVE")
        self.assertEqual(normalize_execution_session_name("LONDON_NEW_YORK_OVERLAP"), "US_OVERLAP")
        self.assertEqual(normalize_execution_session_name("NEW_YORK"), "NY_ACTIVE")
        self.assertEqual(normalize_execution_session_name("ROLLOVER"), "DAILY_BREAK")

    def test_execution_control_default_blocks_daily_break(self) -> None:
        config = ExecutionControlConfig()

        self.assertFalse(config.allowed_sessions["DAILY_BREAK"])
        self.assertTrue(config.allowed_sessions["ASIA_LOW"])


if __name__ == "__main__":
    unittest.main()
