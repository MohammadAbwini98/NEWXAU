from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo


GOLD_SESSION_TIMEZONE = "Asia/Amman"


@dataclass(frozen=True, slots=True)
class MarketSessionDefinition:
    name: str
    start: time
    end: time
    timezone: str = GOLD_SESSION_TIMEZONE
    priority: int = 0
    trading_allowed: bool = True


@dataclass(frozen=True, slots=True)
class MarketSessionState:
    session: str
    timestamp_utc: datetime
    jordan_time: datetime
    trading_allowed: bool
    definition: MarketSessionDefinition | None = None


GOLD_MARKET_SESSIONS: tuple[MarketSessionDefinition, ...] = (
    MarketSessionDefinition("DAILY_BREAK", time(0, 0), time(1, 0), priority=100, trading_allowed=False),
    MarketSessionDefinition("US_OVERLAP", time(16, 0), time(19, 0), priority=80, trading_allowed=True),
    MarketSessionDefinition("LONDON_ACTIVE", time(10, 0), time(16, 0), priority=60, trading_allowed=True),
    MarketSessionDefinition("NY_ACTIVE", time(19, 0), time(0, 0), priority=50, trading_allowed=True),
    MarketSessionDefinition("ASIA_LOW", time(0, 0), time(10, 0), priority=10, trading_allowed=True),
)

GOLD_MARKET_SESSION_NAMES: tuple[str, ...] = tuple(session.name for session in GOLD_MARKET_SESSIONS)
GOLD_MARKET_SESSION_BY_NAME: dict[str, MarketSessionDefinition] = {session.name: session for session in GOLD_MARKET_SESSIONS}


def normalize_gold_session_name(value: object) -> str:
    raw = str(value or "").strip().upper().replace(" ", "_").replace("-", "_").replace("/", "_")
    aliases = {
        "ASIA": "ASIA_LOW",
        "ASIAN": "ASIA_LOW",
        "ASIAN_SESSION": "ASIA_LOW",
        "ASIA_SESSION": "ASIA_LOW",
        "LONDON": "LONDON_ACTIVE",
        "LONDON_SESSION": "LONDON_ACTIVE",
        "NY": "NY_ACTIVE",
        "NEWYORK": "NY_ACTIVE",
        "NEW_YORK": "NY_ACTIVE",
        "NEW_YORK_SESSION": "NY_ACTIVE",
        "US": "US_OVERLAP",
        "US_SESSION": "US_OVERLAP",
        "OVERLAP": "US_OVERLAP",
        "LONDON_NEW_YORK": "US_OVERLAP",
        "LONDON_NEW_YORK_OVERLAP": "US_OVERLAP",
        "LONDON_NY": "US_OVERLAP",
        "LONDON_NY_OVERLAP": "US_OVERLAP",
        "LONDON_NEWYORK_OVERLAP": "US_OVERLAP",
        "ROLLOVER": "DAILY_BREAK",
        "ROLLOVER_SESSION": "DAILY_BREAK",
        "BREAK": "DAILY_BREAK",
        "DAILY_ROLLOVER": "DAILY_BREAK",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in GOLD_MARKET_SESSION_NAMES else "UNKNOWN"


def resolve_gold_market_session(value: datetime | None = None) -> MarketSessionState:
    """Resolve an aware or naive UTC timestamp into the XAUUSD Jordan-time session."""

    utc_ts = _as_utc(value or datetime.now(tz=UTC))
    jordan_time = utc_ts.astimezone(ZoneInfo(GOLD_SESSION_TIMEZONE))
    local_clock = jordan_time.time().replace(tzinfo=None)

    for definition in sorted(GOLD_MARKET_SESSIONS, key=lambda item: item.priority, reverse=True):
        if _contains_time(definition.start, definition.end, local_clock):
            return MarketSessionState(
                session=definition.name,
                timestamp_utc=utc_ts,
                jordan_time=jordan_time,
                trading_allowed=definition.trading_allowed,
                definition=definition,
            )

    return MarketSessionState(
        session="UNKNOWN",
        timestamp_utc=utc_ts,
        jordan_time=jordan_time,
        trading_allowed=False,
        definition=None,
    )


def get_gold_market_session(value: datetime | None = None) -> str:
    return resolve_gold_market_session(value).session


def is_gold_session_trading_allowed(session_name: object) -> bool:
    definition = GOLD_MARKET_SESSION_BY_NAME.get(normalize_gold_session_name(session_name))
    return bool(definition and definition.trading_allowed)


def default_gold_session_permissions() -> dict[str, bool]:
    return {session.name: session.trading_allowed for session in GOLD_MARKET_SESSIONS}


def gold_market_session_config() -> list[dict[str, object]]:
    return [
        {
            "name": session.name,
            "start": session.start.strftime("%H:%M"),
            "end": session.end.strftime("%H:%M"),
            "timezone": session.timezone,
            "priority": session.priority,
            "trading_allowed": session.trading_allowed,
        }
        for session in GOLD_MARKET_SESSIONS
    ]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _contains_time(start: time, end: time, value: time) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= value < end
    return value >= start or value < end
