from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import time
from typing import Any, Awaitable, Callable

import requests
from dateutil import parser

from .config import RuntimeConfig


class CapitalStreamError(RuntimeError):
    """Raised for Capital.com websocket stream failures."""


@dataclass(slots=True)
class CapitalSessionTokens:
    cst: str
    security_token: str


@dataclass(slots=True)
class LivePriceTick:
    instrument: str
    epic: str
    bid: float | None
    ask: float | None
    price: float
    timestamp: datetime
    source: str = "capital.com.websocket"
    raw: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "instrument": self.instrument,
            "epic": self.epic,
            "bid": self.bid,
            "ask": self.ask,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "raw": self.raw or {},
        }


TickCallback = Callable[[LivePriceTick], Awaitable[None]]
StatusCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


def quote_subscription_payload(epic: str, tokens: CapitalSessionTokens) -> dict[str, Any]:
    return {
        "destination": "marketData.subscribe",
        "correlationId": "quote-1",
        "cst": tokens.cst,
        "securityToken": tokens.security_token,
        "payload": {"epics": [epic]},
    }


def ping_service_payload(correlation_id: str, tokens: CapitalSessionTokens) -> dict[str, Any]:
    return {
        "destination": "ping",
        "correlationId": correlation_id,
        "cst": tokens.cst,
        "securityToken": tokens.security_token,
    }


def parse_price_tick(event: dict[str, Any], instrument: str, fallback_epic: str) -> LivePriceTick | None:
    destination = str(event.get("destination", "")).lower()
    if destination and destination != "quote":
        return None

    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None

    bid = _float_or_none(payload.get("bid"))
    ask = _float_or_none(payload.get("ofr", payload.get("ask")))
    price = _float_or_none(payload.get("price", payload.get("mid")))
    if price is None:
        if bid is not None and ask is not None:
            price = (bid + ask) / 2.0
        elif bid is not None:
            price = bid
        elif ask is not None:
            price = ask

    if price is None:
        return None

    timestamp = _parse_timestamp(
        payload.get("timestamp")
        or payload.get("t")
        or payload.get("T")
        or payload.get("utm")
        or payload.get("UTM")
        or payload.get("snapshotTimeUTC")
        or payload.get("snapshotTime")
    )
    epic = str(payload.get("epic") or event.get("epic") or fallback_epic)
    return LivePriceTick(
        instrument=instrument,
        epic=epic,
        bid=bid,
        ask=ask,
        price=float(price),
        timestamp=timestamp,
        raw=payload,
    )


class CapitalLivePriceStream:
    def __init__(
        self,
        runtime: RuntimeConfig,
        on_tick: TickCallback,
        on_status: StatusCallback | None = None,
    ) -> None:
        self.runtime = runtime
        self.on_tick = on_tick
        self.on_status = on_status
        self._running = False
        self._session = requests.Session()

    async def stream_forever(self) -> None:
        self._running = True
        while self._running:
            retry_seconds = max(self.runtime.capitalcom_stream_retry_seconds, 1)
            status_payload = {"message": "Capital.com stream closed.", "epic": self.runtime.capitalcom_epic}
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                status_payload = {"message": str(exc), "epic": self.runtime.capitalcom_epic}
            if self._running:
                if self.on_status is not None:
                    await self.on_status("RECONNECTING", {**status_payload, "retry_seconds": retry_seconds})
                await asyncio.sleep(retry_seconds)

    async def stop(self) -> None:
        self._running = False

    async def _connect_once(self) -> None:
        import websockets

        tokens = await asyncio.to_thread(self._authenticate)
        payload = quote_subscription_payload(self.runtime.capitalcom_epic, tokens)
        if self.on_status is not None:
            await self.on_status("CONNECTING", {"epic": self.runtime.capitalcom_epic})

        async with websockets.connect(
            self.runtime.capitalcom_stream_url,
            ping_interval=None,
            close_timeout=5,
        ) as websocket:
            await websocket.send(json.dumps(payload))
            if self.on_status is not None:
                await self.on_status("STREAMING", {"epic": self.runtime.capitalcom_epic})

            ping_task = asyncio.create_task(self._send_keepalive_pings(websocket, tokens))
            try:
                while self._running:
                    receive_task = asyncio.create_task(websocket.recv())
                    done, _ = await asyncio.wait({receive_task, ping_task}, return_when=asyncio.FIRST_COMPLETED)
                    if ping_task in done:
                        if not receive_task.done():
                            receive_task.cancel()
                            with suppress(asyncio.CancelledError):
                                await receive_task
                        ping_task.result()
                        raise CapitalStreamError("Capital.com keepalive ping worker stopped unexpectedly.")
                    message = receive_task.result()
                    await self._handle_stream_message(message)
            finally:
                ping_task.cancel()
                with suppress(asyncio.CancelledError):
                    await ping_task

    async def _handle_stream_message(self, message: str | bytes) -> None:
        if not self._running:
            return
        event = json.loads(message)
        if event.get("status") == "ERROR":
            raise CapitalStreamError(f"Capital.com stream error: {event}")
        tick = parse_price_tick(event, self.runtime.instrument, self.runtime.capitalcom_epic)
        if tick is not None:
            await self.on_tick(tick)

    async def _send_keepalive_pings(self, websocket: Any, tokens: CapitalSessionTokens) -> None:
        interval = max(int(getattr(self.runtime, "capitalcom_stream_ping_seconds", 540) or 540), 1)
        counter = 0
        while self._running:
            await asyncio.sleep(interval)
            if not self._running:
                return
            counter += 1
            await websocket.send(json.dumps(ping_service_payload(f"ping-{counter}", tokens)))

    def _authenticate(self) -> CapitalSessionTokens:
        if not self.runtime.capitalcom_api_key or not self.runtime.capitalcom_identifier or not self.runtime.capitalcom_password:
            raise CapitalStreamError("Capital.com stream credentials are missing.")

        base = self.runtime.capitalcom_api_base.rstrip("/")
        if not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        response = self._session.post(
            f"{base}/session",
            json={
                "identifier": self.runtime.capitalcom_identifier,
                "password": self.runtime.capitalcom_password,
                "encryptedPassword": self.runtime.capitalcom_use_encrypted_password,
            },
            headers={"X-CAP-API-KEY": self.runtime.capitalcom_api_key},
            timeout=20,
        )
        response.raise_for_status()
        cst = response.headers.get("CST")
        token = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not token:
            raise CapitalStreamError("Capital.com auth response did not include CST/X-SECURITY-TOKEN.")
        return CapitalSessionTokens(cst=cst, security_token=token)


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime:
    if value in (None, ""):
        return datetime.now(tz=UTC)
    if isinstance(value, (int, float)):
        numeric = int(value)
        unit = 1000 if abs(numeric) > 10_000_000_000 else 1
        return datetime.fromtimestamp(numeric / unit, tz=UTC)
    text = str(value).strip()
    if text.isdigit():
        numeric = int(text)
        unit = 1000 if abs(numeric) > 10_000_000_000 else 1
        return datetime.fromtimestamp(numeric / unit, tz=UTC)
    dt = parser.isoparse(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)
