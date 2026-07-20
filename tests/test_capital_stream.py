from __future__ import annotations

import os
import sys
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.capital_stream import (
    CapitalLivePriceStream,
    CapitalSessionTokens,
    ping_service_payload,
    parse_price_tick,
    quote_subscription_payload,
)
from gold_signal_system.config import RuntimeConfig


class CapitalStreamTests(unittest.TestCase):
    def test_quote_subscription_payload_matches_capital_stream_contract(self) -> None:
        payload = quote_subscription_payload("GOLD", CapitalSessionTokens(cst="cst", security_token="token"))

        self.assertEqual(payload["destination"], "marketData.subscribe")
        self.assertEqual(payload["cst"], "cst")
        self.assertEqual(payload["securityToken"], "token")
        self.assertEqual(payload["payload"]["epics"], ["GOLD"])

    def test_ping_service_payload_matches_capital_stream_contract(self) -> None:
        payload = ping_service_payload("ping-1", CapitalSessionTokens(cst="cst", security_token="token"))

        self.assertEqual(payload["destination"], "ping")
        self.assertEqual(payload["correlationId"], "ping-1")
        self.assertEqual(payload["cst"], "cst")
        self.assertEqual(payload["securityToken"], "token")

    def test_parse_quote_tick_uses_bid_ask_mid_price(self) -> None:
        tick = parse_price_tick(
            {
                "destination": "quote",
                "payload": {
                    "epic": "GOLD",
                    "bid": 2350.10,
                    "ofr": 2350.30,
                    "timestamp": "2026-06-07T10:00:00Z",
                },
            },
            instrument="XAUUSD",
            fallback_epic="XAUUSD",
        )

        self.assertIsNotNone(tick)
        assert tick is not None
        self.assertEqual(tick.instrument, "XAUUSD")
        self.assertEqual(tick.epic, "GOLD")
        self.assertAlmostEqual(tick.price, 2350.20)
        self.assertEqual(tick.timestamp, datetime(2026, 6, 7, 10, 0, tzinfo=UTC))

    def test_parse_quote_tick_accepts_epoch_millisecond_timestamp(self) -> None:
        tick = parse_price_tick(
            {
                "destination": "quote",
                "payload": {
                    "bid": "2351.50",
                    "utm": 1780826400000,
                },
            },
            instrument="XAUUSD",
            fallback_epic="GOLD",
        )

        self.assertIsNotNone(tick)
        assert tick is not None
        self.assertEqual(tick.epic, "GOLD")
        self.assertAlmostEqual(tick.price, 2351.50)


class CapitalStreamKeepaliveTests(unittest.IsolatedAsyncioTestCase):
    async def test_keepalive_worker_sends_capital_ping_payload(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            capitalcom_stream_ping_seconds=2,
        )
        stream = CapitalLivePriceStream(runtime, lambda tick: None)  # type: ignore[arg-type]
        stream._running = True

        class FakeWebSocket:
            def __init__(self) -> None:
                self.sent: list[str] = []

            async def send(self, payload: str) -> None:
                self.sent.append(payload)
                stream._running = False

        async def fast_sleep(_: float) -> None:
            return None

        websocket = FakeWebSocket()
        with patch("gold_signal_system.capital_stream.asyncio.sleep", new=fast_sleep):
            await stream._send_keepalive_pings(websocket, CapitalSessionTokens(cst="cst", security_token="token"))

        self.assertEqual(len(websocket.sent), 1)
        self.assertIn('"destination": "ping"', websocket.sent[0])
        self.assertIn('"correlationId": "ping-1"', websocket.sent[0])


if __name__ == "__main__":
    unittest.main()
