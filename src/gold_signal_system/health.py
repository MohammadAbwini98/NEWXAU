from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .contracts import Candle


@dataclass(slots=True)
class SystemHealthEvent:
    component: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    resolved_at: datetime | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class SystemHealthService:
    def __init__(self, storage=None) -> None:
        self.storage = storage
        self.events: list[SystemHealthEvent] = []
        self.model_latencies: dict[str, float] = {}
        self.model_failures: dict[str, int] = {}
        self.last_validation_at: datetime | None = None
        self.last_news_sync_status: str = "UNKNOWN"
        self.market_data_status: str = "UNKNOWN"
        self.capital_stream_status: str = "UNKNOWN"

    def attach_storage(self, storage) -> None:
        self.storage = storage

    def check(self, candles: list[Candle], timeframe: str = "5m", now: datetime | None = None) -> dict[str, Any]:
        now = (now or datetime.now(tz=UTC)).astimezone(UTC)
        status = "HEALTHY"
        failed: list[str] = []
        last_candle = candles[-1].candle_time.astimezone(UTC) if candles else None
        # Candle-freshness windows must scale with the timeframe: a 1h candle only
        # arrives every 60 min, so a fixed 24-min "critical" age (tuned for 5m) flags
        # normal 1h/4h data as stale and blocks every signal. Scale off bar duration.
        tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240}.get(timeframe, 5)
        max_age = timedelta(minutes=tf_minutes * 1.5 + 2)
        critical_age = timedelta(minutes=tf_minutes * 3.0 + 4)

        if not last_candle:
            status = "CRITICAL"
            failed.append("No candles available.")
        else:
            age = now - last_candle
            if age > critical_age:
                status = "CRITICAL"
                failed.append(f"No new {timeframe} candle for {int(age.total_seconds() // 60)} minutes.")
            elif age > max_age and status != "CRITICAL":
                status = "WARNING"
                failed.append(f"No new {timeframe} candle for {int(age.total_seconds() // 60)} minutes.")

        if self.model_failures and all(count > 0 for count in self.model_failures.values()):
            status = "CRITICAL"
            failed.append("All tracked models have recent failures.")

        event = SystemHealthEvent(
            component="system",
            status=status,
            message="; ".join(failed) if failed else "All monitored components are ready.",
            details={
                "last_candle_time": last_candle.isoformat() if last_candle else None,
                "model_latencies": self.model_latencies,
                "model_failures": self.model_failures,
                "market_data_status": self.market_data_status,
                "capital_stream_status": self.capital_stream_status,
                "last_validation_at": self.last_validation_at.isoformat() if self.last_validation_at else None,
                "last_news_sync_status": self.last_news_sync_status,
            },
        )
        self.events.append(event)
        if self.storage is not None:
            try:
                self.storage.save_health_snapshot("system", status, event.details, failure_count=len(failed))
                if status in {"WARNING", "CRITICAL"}:
                    self.storage.save_health_event("system", status, event.message, event.details)
            except Exception:
                pass
        return {
            "overall_status": status,
            "failed_components": failed,
            "last_candle_time": event.details["last_candle_time"],
            "details": event.details,
            "checked_at": event.created_at.isoformat(),
        }

    def check_trading_readiness(self, candles: list[Candle], timeframe: str = "5m") -> dict[str, Any]:
        health = self.check(candles, timeframe)
        health["trading_allowed"] = health["overall_status"] != "CRITICAL"
        return health

    def record_model_latency(self, model_name: str, latency_ms: float) -> None:
        self.model_latencies[model_name.lower()] = latency_ms
        if self.storage is not None:
            try:
                self.storage.save_health_snapshot(model_name.lower(), "HEALTHY", {"source": "model_latency"}, latency_ms=latency_ms)
            except Exception:
                pass

    def record_model_failure(self, model_name: str) -> None:
        key = model_name.lower()
        self.model_failures[key] = self.model_failures.get(key, 0) + 1
        if self.storage is not None:
            try:
                self.storage.save_health_event(key, "WARNING", "Model failure recorded.", {"failure_count": self.model_failures[key]})
                self.storage.save_health_snapshot(key, "WARNING", {"source": "model_failure"}, failure_count=self.model_failures[key])
            except Exception:
                pass

    def record_event(self, component: str, status: str, message: str, details: dict[str, Any] | None = None) -> None:
        event = SystemHealthEvent(
            component=component,
            status=status,
            message=message,
            details=details or {},
        )
        self.events.append(event)
        if self.storage is not None:
            try:
                if status in {"WARNING", "CRITICAL", "FAILED"}:
                    self.storage.save_health_event(component, status, message, details or {})
                self.storage.save_health_snapshot(component, status, details or {})
            except Exception:
                pass

    def events_payload(self, limit: int = 100) -> dict[str, Any]:
        rows = self.events[-limit:]
        return {"total": len(self.events), "items": [event.model_dump() for event in reversed(rows)]}
