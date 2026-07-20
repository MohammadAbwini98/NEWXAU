from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import RuntimeConfig


_DAY_TO_INDEX = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6,
}


@dataclass(frozen=True)
class MarketHoursState:
    is_open: bool
    now: datetime
    timezone: str
    reason: str
    weekly_open: datetime
    weekly_close: datetime
    closure_key: str | None = None
    next_transition: datetime | None = None


def market_hours_state(runtime: RuntimeConfig, now: datetime | None = None) -> MarketHoursState:
    timezone_name = runtime.market_hours_timezone or "UTC"
    tz = ZoneInfo(timezone_name)
    local_now = (now or datetime.now(tz=UTC)).astimezone(tz)
    weekly_open_minute = _parse_weekly_minute(runtime.market_weekly_open)
    weekly_close_minute = _parse_weekly_minute(runtime.market_weekly_close)
    current_minute = local_now.weekday() * 1440 + local_now.hour * 60 + local_now.minute
    week_start = _week_start(local_now)
    weekly_open = week_start + timedelta(minutes=weekly_open_minute)
    weekly_close = week_start + timedelta(minutes=weekly_close_minute)

    if weekly_open_minute < weekly_close_minute:
        is_open = weekly_open_minute <= current_minute < weekly_close_minute
        if is_open:
            next_transition = weekly_close
            reason = "Market is inside the configured weekly trading window."
            closure_key = None
        elif current_minute < weekly_open_minute:
            next_transition = weekly_open
            reason = "Market is before the configured weekly open."
            closure_key = _closure_key(week_start - timedelta(days=7) + timedelta(minutes=weekly_close_minute))
        else:
            next_transition = weekly_open + timedelta(days=7)
            reason = "Market is after the configured weekly close."
            closure_key = _closure_key(weekly_close)
    else:
        is_open = current_minute >= weekly_open_minute or current_minute < weekly_close_minute
        if is_open:
            if current_minute >= weekly_open_minute:
                next_transition = weekly_close + timedelta(days=7)
                weekly_close = weekly_close + timedelta(days=7)
            else:
                next_transition = weekly_close
                weekly_open = weekly_open - timedelta(days=7)
            reason = "Market is inside the configured weekly trading window."
            closure_key = None
        else:
            next_transition = weekly_open
            reason = "Market is between the configured weekly close and next open."
            closure_key = _closure_key(weekly_close)

    if is_open and runtime.market_daily_break_enabled:
        daily_break = _daily_break_state(runtime, local_now)
        if daily_break is not None:
            break_start, break_end = daily_break
            is_open = False
            reason = "Market is inside the configured daily broker maintenance break."
            closure_key = _closure_key(break_start)
            next_transition = break_end

    return MarketHoursState(
        is_open=is_open,
        now=local_now,
        timezone=timezone_name,
        reason=reason,
        weekly_open=weekly_open,
        weekly_close=weekly_close,
        closure_key=closure_key,
        next_transition=next_transition,
    )


def _parse_weekly_minute(value: str) -> int:
    day_text, time_text = str(value or "").strip().upper().split(maxsplit=1)
    day_index = _DAY_TO_INDEX[day_text[:3]]
    hour_text, minute_text = time_text.split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid market hour value: {value}")
    return day_index * 1440 + hour * 60 + minute


def _daily_break_state(runtime: RuntimeConfig, now: datetime) -> tuple[datetime, datetime] | None:
    start_hour, start_minute = _parse_clock(runtime.market_daily_break_start)
    end_hour, end_minute = _parse_clock(runtime.market_daily_break_end)
    start = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end = now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    if end <= start:
        if now >= start:
            end = end + timedelta(days=1)
        else:
            start = start - timedelta(days=1)
    if start <= now < end:
        return start, end
    return None


def _parse_clock(value: str) -> tuple[int, int]:
    hour_text, minute_text = str(value or "").strip().split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid market clock value: {value}")
    return hour, minute


def _week_start(value: datetime) -> datetime:
    midnight = value.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=value.weekday())


def _closure_key(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
