from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import logging
from typing import Any

from .models import ActionLevel, MacroEventModel

logger = logging.getLogger(__name__)


RISK_WINDOWS: dict[str, dict[str, Any]] = {
    "CPI": {"before": 30, "after": 15, "action": ActionLevel.BLOCK_NEW_TRADES.value},
    "FOMC_RATE_DECISION": {"before": 60, "after": 30, "action": ActionLevel.BLOCK_NEW_TRADES.value},
    "FOMC_MINUTES": {"before": 30, "after": 30, "action": ActionLevel.BLOCK_NEW_TRADES.value},
    "NFP": {"before": 30, "after": 15, "action": ActionLevel.BLOCK_NEW_TRADES.value},
    "FED_SPEECH": {"before": 15, "after": 15, "action": ActionLevel.RISK_REDUCE.value},
    "WAR_ESCALATION": {"before": 0, "after": 360, "action": ActionLevel.MANUAL_REVIEW.value},
    "GEOPOLITICAL_RISK": {"before": 0, "after": 240, "action": ActionLevel.RISK_REDUCE.value},
}


def generate_macro_event_hash(event_type: str, scheduled_at: datetime, title: str | None = None) -> str:
    scheduled = scheduled_at.astimezone(UTC).replace(microsecond=0).isoformat()
    base = f"{event_type.upper()}|{scheduled}|{(title or '').strip().lower()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def calculate_risk_window(event_type: str, scheduled_at: datetime) -> dict[str, Any]:
    config = RISK_WINDOWS.get(event_type.upper(), {"before": 0, "after": 0, "action": ActionLevel.INFO_ONLY.value})
    before = int(config["before"])
    after = int(config["after"])
    scheduled = scheduled_at if scheduled_at.tzinfo else scheduled_at.replace(tzinfo=UTC)
    return {
        "event_type": event_type.upper(),
        "scheduled_at": scheduled.isoformat(),
        "window_start": (scheduled - timedelta(minutes=before)).isoformat(),
        "window_end": (scheduled + timedelta(minutes=after)).isoformat(),
        "block_before_minutes": before,
        "block_after_minutes": after,
        "default_action": config["action"],
    }


def current_risk_window(events: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    active: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for event in events:
        scheduled = _parse_dt(event.get("scheduled_at"))
        if scheduled is None:
            continue
        window = calculate_risk_window(str(event.get("event_type") or "UNKNOWN"), scheduled)
        start = _parse_dt(window["window_start"])
        end = _parse_dt(window["window_end"])
        if start and end and start <= now <= end:
            active.append({**event, "risk_window": window, "minutes_to_event": int((scheduled - now).total_seconds() / 60)})
        elif scheduled > now:
            upcoming.append({**event, "risk_window": window, "minutes_to_event": int((scheduled - now).total_seconds() / 60)})
    active.sort(key=lambda item: abs(int(item.get("minutes_to_event") or 0)))
    upcoming.sort(key=lambda item: int(item.get("minutes_to_event") or 999999))
    if active:
        event = active[0]
        return {
            "status": "ACTIVE",
            "action_level": event["risk_window"]["default_action"],
            "event": event,
            "reason": f"{event.get('event_type')} risk window is active.",
        }
    if upcoming:
        event = upcoming[0]
        return {
            "status": "UPCOMING",
            "action_level": ActionLevel.INFO_ONLY.value,
            "event": event,
            "reason": f"{event.get('event_type')} in {event.get('minutes_to_event')} minutes.",
        }
    return {"status": "CLEAR", "action_level": ActionLevel.INFO_ONLY.value, "event": None, "reason": "No active macro risk window."}


class MacroEventIngestor:
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def ingest_event(self, event: MacroEventModel) -> int | None:
        event_hash = generate_macro_event_hash(event.event_type, event.scheduled_at, event.title)
        logger.info("Ingesting macro event %s at %s", event.event_type, event.scheduled_at)
        return self.repository.save_macro_event(event, event_hash)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except Exception:
        return None
