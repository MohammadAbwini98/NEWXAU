from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import requests


@dataclass(slots=True)
class EconomicNewsEvent:
    source: str
    event_name: str
    country: str
    currency: str
    impact: str
    scheduled_at: datetime
    event_id: str | None = None
    block_before_minutes: int = 30
    block_after_minutes: int = 30
    is_active: bool = True
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None
    status: str = "SCHEDULED"

    def model_dump(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_id": self.event_id or self._event_id(),
            "title": self.event_name,
            "event_name": self.event_name,
            "country": self.country,
            "currency": self.currency,
            "impact": self.impact,
            "event_time": self.scheduled_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat(),
            "block_before_minutes": self.block_before_minutes,
            "block_after_minutes": self.block_after_minutes,
            "is_active": self.is_active,
            "actual": self.actual,
            "forecast": self.forecast,
            "previous": self.previous,
            "status": self.status,
        }

    def _event_id(self) -> str:
        safe_title = "".join(ch.lower() if ch.isalnum() else "_" for ch in self.event_name).strip("_")
        return f"{self.source}:{self.currency}:{safe_title}:{int(self.scheduled_at.timestamp())}"


@dataclass(slots=True)
class NewsRiskResult:
    status: str
    reason: str
    event_name: str | None = None
    minutes_to_event: int | None = None
    minutes_since_event: int | None = None
    cooldown_minutes_after: int = 15
    confidence_multiplier: float = 1.0
    event: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "event_name": self.event_name,
            "minutes_to_event": self.minutes_to_event,
            "minutes_since_event": self.minutes_since_event,
            "cooldown_minutes_after": self.cooldown_minutes_after,
            "confidence_multiplier": self.confidence_multiplier,
            "event": self.event,
        }


class INewsProvider(Protocol):
    mode: str

    def get_events(self, start: datetime, end: datetime) -> list[EconomicNewsEvent]:
        ...

    def sync(self) -> dict[str, Any]:
        ...


class ManualNewsProvider:
    mode = "manual"

    def __init__(self) -> None:
        self.events: list[EconomicNewsEvent] = []

    def add_event(self, event: EconomicNewsEvent) -> None:
        if event.scheduled_at.tzinfo is None:
            event.scheduled_at = event.scheduled_at.replace(tzinfo=UTC)
        self.events.append(event)

    def get_events(self, start: datetime, end: datetime) -> list[EconomicNewsEvent]:
        return [
            event
            for event in self.events
            if start <= event.scheduled_at.astimezone(UTC) <= end
            and event.is_active
        ]

    def sync(self) -> dict[str, Any]:
        return {"status": "MANUAL_PROVIDER_READY", "mode": self.mode, "events": len(self.events)}


class MockNewsProvider(ManualNewsProvider):
    mode = "mock"

    def __init__(self, now: datetime | None = None) -> None:
        super().__init__()
        now = (now or datetime.now(tz=UTC)).astimezone(UTC)
        self.add_event(
            EconomicNewsEvent(
                source="mock",
                event_name="Mock US CPI",
                country="US",
                currency="USD",
                impact="HIGH",
                scheduled_at=now + timedelta(hours=4),
                event_id="mock-us-cpi",
            )
        )

    def sync(self) -> dict[str, Any]:
        return {"status": "MOCK_PROVIDER_READY", "mode": self.mode, "events": len(self.events)}


class RealEconomicCalendarProvider(ManualNewsProvider):
    mode = "real"

    def __init__(self, url: str | None = None, timeout_seconds: int = 20) -> None:
        super().__init__()
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.last_error: str | None = None

    def sync(self) -> dict[str, Any]:
        if not self.url:
            self.last_error = "NEWS_PROVIDER_URL is not configured."
            return {"status": "ERROR", "mode": self.mode, "message": self.last_error, "events": len(self.events)}
        try:
            response = requests.get(self.url, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            raw_events = payload.get("events", payload if isinstance(payload, list) else [])
            self.events = [event for event in (self._parse_event(item) for item in raw_events) if event is not None]
            self.last_error = None
            return {"status": "OK", "mode": self.mode, "events": len(self.events)}
        except Exception as exc:
            self.last_error = str(exc)
            return {"status": "ERROR", "mode": self.mode, "message": self.last_error, "events": len(self.events)}

    def _parse_event(self, item: dict[str, Any]) -> EconomicNewsEvent | None:
        event_time = item.get("event_time") or item.get("scheduled_at") or item.get("time")
        if not event_time:
            return None
        try:
            scheduled_at = datetime.fromisoformat(str(event_time).replace("Z", "+00:00")).astimezone(UTC)
        except Exception:
            return None
        return EconomicNewsEvent(
            source=str(item.get("source", "real")),
            event_name=str(item.get("title") or item.get("event_name") or item.get("name") or "Unknown event"),
            country=str(item.get("country", "US")),
            currency=str(item.get("currency", "USD")),
            impact=str(item.get("impact", "HIGH")).upper(),
            scheduled_at=scheduled_at,
            event_id=str(item.get("event_id") or item.get("id") or ""),
            block_before_minutes=int(item.get("block_before_minutes", 30)),
            block_after_minutes=int(item.get("block_after_minutes", 30)),
            is_active=bool(item.get("is_active", True)),
            actual=item.get("actual"),
            forecast=item.get("forecast"),
            previous=item.get("previous"),
            status=str(item.get("status", "SCHEDULED")),
        )


class EconomicNewsFilter:
    MARKET_KEYWORDS = (
        "FOMC",
        "FED",
        "CPI",
        "PPI",
        "NFP",
        "NONFARM",
        "UNEMPLOYMENT",
        "GDP",
        "ISM",
        "RETAIL SALES",
        "JOBLESS",
        "PAYROLL",
        "POWELL",
        "ETHEREUM",
        "ETH",
        "CRYPTO",
        "ETF",
    )

    def __init__(
        self,
        provider: INewsProvider | None = None,
        block_before_minutes: int = 30,
        block_after_minutes: int = 15,
        mode: str = "manual",
        block_mode: str = "block",
    ) -> None:
        self.provider = provider or build_news_provider(mode)
        self.mode = getattr(self.provider, "mode", mode)
        self.block_before_minutes = block_before_minutes
        self.block_after_minutes = block_after_minutes
        self.block_mode = block_mode
        self.last_sync_status = f"{self.mode.upper()}_PROVIDER_READY"

    def current_risk(self, now: datetime | None = None) -> NewsRiskResult:
        now = (now or datetime.now(tz=UTC)).astimezone(UTC)
        window_start = now - timedelta(minutes=max(self.block_after_minutes, 60))
        window_end = now + timedelta(minutes=max(self.block_before_minutes, 60))
        events = sorted(self.provider.get_events(window_start, window_end), key=lambda e: e.scheduled_at)

        for event in events:
            if not self._is_market_relevant(event):
                continue
            scheduled = event.scheduled_at.astimezone(UTC)
            minutes_to = int((scheduled - now).total_seconds() // 60)
            minutes_since = int((now - scheduled).total_seconds() // 60)
            before_window = event.block_before_minutes or self.block_before_minutes
            after_window = event.block_after_minutes or self.block_after_minutes
            if event.impact.upper() == "HIGH" and 0 <= minutes_to <= before_window:
                status = "BLOCKED" if self.block_mode.lower() == "block" else "CAUTION"
                return NewsRiskResult(
                    status=status,
                    reason=f"High-impact {event.currency} {event.event_name} event in {minutes_to} minutes",
                    event_name=event.event_name,
                    minutes_to_event=minutes_to,
                    cooldown_minutes_after=after_window,
                    confidence_multiplier=0.0 if status == "BLOCKED" else 0.65,
                    event=event.model_dump(),
                )
            if event.impact.upper() == "HIGH" and 0 <= minutes_since <= after_window:
                status = "BLOCKED" if self.block_mode.lower() == "block" else "CAUTION"
                return NewsRiskResult(
                    status=status,
                    reason=f"High-impact {event.currency} {event.event_name} cooldown active",
                    event_name=event.event_name,
                    minutes_since_event=minutes_since,
                    cooldown_minutes_after=after_window,
                    confidence_multiplier=0.0 if status == "BLOCKED" else 0.65,
                    event=event.model_dump(),
                )
            if event.impact.upper() == "MEDIUM" and 0 <= minutes_to <= self.block_before_minutes:
                return NewsRiskResult(
                    status="CAUTION",
                    reason=f"Medium-impact {event.currency} {event.event_name} event nearby",
                    event_name=event.event_name,
                    minutes_to_event=minutes_to,
                    cooldown_minutes_after=after_window,
                    confidence_multiplier=0.85,
                    event=event.model_dump(),
                )

        return NewsRiskResult(status="SAFE", reason="No configured high-impact market news risk.", confidence_multiplier=1.0)

    def upcoming(self, hours: int = 24, now: datetime | None = None) -> list[dict[str, Any]]:
        now = (now or datetime.now(tz=UTC)).astimezone(UTC)
        events = self.provider.get_events(now, now + timedelta(hours=hours))
        return [event.model_dump() for event in sorted(events, key=lambda item: item.scheduled_at)]

    def sync(self) -> dict[str, Any]:
        result = self.provider.sync()
        self.last_sync_status = str(result.get("status", "UNKNOWN"))
        return result

    def _is_market_relevant(self, event: EconomicNewsEvent) -> bool:
        if event.currency.upper() in {"USD", "ETH"}:
            return True
        upper_name = event.event_name.upper()
        return any(keyword in upper_name for keyword in self.MARKET_KEYWORDS)


ManualEconomicCalendarProvider = ManualNewsProvider


def build_news_provider(mode: str, url: str | None = None) -> INewsProvider:
    normalized = (mode or "manual").strip().lower()
    if normalized == "mock":
        return MockNewsProvider()
    if normalized == "real":
        return RealEconomicCalendarProvider(url=url)
    return ManualNewsProvider()
