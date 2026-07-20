from __future__ import annotations

import asyncio
from contextlib import suppress
import csv
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from dateutil import parser
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

from .backtesting import BacktestConfig, BacktestingEngine
from .capital_execution import CapitalExecutionService
from .capital_stream import CapitalLivePriceStream, LivePriceTick
from .config import ModelWeights, RiskLimits, RuntimeConfig
from .contracts import EXECUTION_CONTROL_SESSIONS, ExecutionControlConfig, FinalRecommendation, MarketContext
from .execution_control import ExecutionControlService
from .news_filter import EconomicNewsEvent
from .news_intelligence.models import MacroEventModel
from .event_bus import EventBus
from .market_hours import MarketHoursState, market_hours_state
from .market_sessions import gold_market_session_config
from .optimization import ThresholdOptimizationService
from .pipeline import GoldSignalSystem
from .replay import SignalReplayService
from .startup_state import bootstrap_runtime_state
from .storage import SignalOutcome
from .utils import generate_synthetic_candles
from .walk_forward import WalkForwardBacktestService, WalkForwardConfig
from .strategy_brain import StrategyThresholdProfile

app = FastAPI(title="XAUUSD Signal System API", version="1.0.0")
runtime = RuntimeConfig()
system = GoldSignalSystem(runtime=runtime)
event_bus = EventBus()
replay_service = SignalReplayService()
walk_forward_service = WalkForwardBacktestService(system, reports_dir=runtime.reports_dir)
optimization_service = ThresholdOptimizationService(walk_forward_service, storage=system.storage)
execution_control_service = ExecutionControlService(system.storage)
execution_service = CapitalExecutionService(runtime=runtime, storage=system.storage, execution_control=execution_control_service)
background_cycle_task: asyncio.Task | None = None
price_stream_task: asyncio.Task | None = None
price_stream: CapitalLivePriceStream | None = None
market_supervisor_task: asyncio.Task | None = None
market_close_backtest_task: asyncio.Task | None = None
last_market_close_backtest_key: str | None = None
latest_price_tick: dict[str, Any] | None = None
latest_price_stream_status: dict[str, Any] = {"status": "WAITING_FOR_STREAM"}
background_cycle_status: dict[str, Any] = {
    "status": "WAITING_TO_START",
    "last_started_at": None,
    "last_success_at": None,
    "last_error_at": None,
    "last_error": None,
    "last_signal_time": None,
    "last_session": None,
    "consecutive_errors": 0,
}
seed_lock = asyncio.Lock()
cycle_execution_lock = asyncio.Lock()
broker_execution_lock = asyncio.Lock()


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _update_background_cycle_status(**updates: Any) -> dict[str, Any]:
    background_cycle_status.update(updates)
    background_cycle_status["updated_at"] = _now_iso()
    return dict(background_cycle_status)


def _background_cycle_stale_after_seconds() -> int:
    interval = max(int(getattr(runtime, "live_cycle_interval_seconds", 300) or 300), 5)
    return max(interval * 2 + 60, 600)


def _parse_optional_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        with suppress(Exception):
            return parser.isoparse(value).astimezone(UTC)
    return None


def _background_cycle_health() -> dict[str, Any]:
    payload = dict(background_cycle_status)
    payload["enabled"] = bool(runtime.enable_background_cycle_runner)
    payload["task_running"] = bool(background_cycle_task and not background_cycle_task.done())
    payload["stale_after_seconds"] = _background_cycle_stale_after_seconds()

    if not runtime.enable_background_cycle_runner:
        payload["status"] = "DISABLED"
        payload["healthy"] = True
        return payload

    now = datetime.now(tz=UTC)
    last_success = _parse_optional_datetime(payload.get("last_success_at"))
    last_started = _parse_optional_datetime(payload.get("last_started_at"))
    age_source = last_success or last_started
    age_seconds = int((now - age_source).total_seconds()) if age_source else None
    payload["age_seconds"] = age_seconds

    status = str(payload.get("status") or "UNKNOWN").upper()
    if age_seconds is not None and age_seconds > payload["stale_after_seconds"]:
        payload["status"] = "STALE"
        payload["healthy"] = False
        payload["message"] = f"Background cycle has not completed successfully for {age_seconds} seconds."
    elif status in {"ERROR", "FAILED"}:
        payload["healthy"] = False
        payload["message"] = payload.get("last_error") or "Background cycle reported an error."
    elif payload["task_running"]:
        payload["healthy"] = True
        payload["message"] = "Background cycle worker is running."
    else:
        payload["status"] = "STOPPED"
        payload["healthy"] = False
        payload["message"] = "Background cycle worker is not running."
    return payload


def _record_background_cycle_error(exc: BaseException, *, source: str = "background_cycle") -> dict[str, Any]:
    errors = int(background_cycle_status.get("consecutive_errors") or 0) + 1
    severity = "CRITICAL" if errors >= 3 else "WARNING"
    details = _update_background_cycle_status(
        status="ERROR",
        last_error_at=_now_iso(),
        last_error=str(exc),
        consecutive_errors=errors,
    )
    details["source"] = source
    with suppress(Exception):
        system.health_service.record_event(source, severity, f"Background cycle failed: {exc}", details)
    return details


async def _restart_background_cycle_after_failure() -> None:
    global background_cycle_task
    if not runtime.enable_background_cycle_runner:
        return
    await asyncio.sleep(1)
    if background_cycle_task is not None and not background_cycle_task.done():
        return
    background_cycle_task = asyncio.create_task(_background_live_cycle_runner())
    background_cycle_task.add_done_callback(_background_cycle_done)
    _update_background_cycle_status(status="RESTARTED")


def _background_cycle_done(task: asyncio.Task) -> None:
    if task.cancelled():
        _update_background_cycle_status(status="STOPPED")
        return
    exc = task.exception()
    if exc is None:
        _update_background_cycle_status(status="STOPPED")
        return
    _record_background_cycle_error(exc, source="background_cycle_task")
    with suppress(RuntimeError):
        asyncio.get_running_loop().create_task(_restart_background_cycle_after_failure())


def _execution_control_service() -> ExecutionControlService:
    global execution_control_service
    if execution_control_service.storage is not system.storage:
        execution_control_service = ExecutionControlService(system.storage)
    if getattr(execution_service, "execution_control", None) is not execution_control_service:
        execution_service.execution_control = execution_control_service
    return execution_control_service


async def _publish_cycle_events(result: dict[str, Any]) -> None:
    latest = result["recommendation"]
    now = datetime.now(tz=UTC).isoformat()
    await event_bus.publish(
        {
            "event": "signal.updated",
            "occurred_at": now,
            "data": latest,
        }
    )
    await event_bus.publish(
        {
            "event": "risk.blocked" if latest.get("status", "").startswith("BLOCKED") else "risk.passed",
            "occurred_at": now,
            "data": {
                "status": latest.get("status"),
                "risk_status": latest.get("risk_status"),
                "blocked_reasons": latest.get("blocked_reasons", []),
            },
        }
    )


async def _publish_execution_event(result: dict[str, Any]) -> None:
    await event_bus.publish(
        {
            "event": "execution.updated",
            "occurred_at": datetime.now(tz=UTC).isoformat(),
            "data": result,
        }
    )


async def _publish_price_tick(tick: LivePriceTick) -> None:
    global latest_price_tick, latest_price_stream_status
    latest_price_tick = tick.model_dump()
    latest_price_stream_status = {
        "status": "LIVE",
        "epic": tick.epic,
        "updated_at": tick.timestamp.isoformat(),
    }
    with suppress(Exception):
        result = await asyncio.to_thread(execution_service.refresh_execution_outcomes, latest_price_tick)
        if result.get("updated"):
            await _publish_execution_event({"status": "OUTCOMES_REFRESHED", **result})
    with suppress(Exception):
        result = await asyncio.to_thread(execution_service.process_pending_entries, latest_price_tick)
        if result.get("processed"):
            await _publish_execution_event({"status": "PENDING_ENTRIES_PROCESSED", **result})
    await event_bus.publish(
        {
            "event": "price.tick",
            "occurred_at": tick.timestamp.isoformat(),
            "data": latest_price_tick,
        }
    )


async def _publish_price_stream_status(status: str, data: dict[str, Any]) -> None:
    global latest_price_stream_status
    latest_price_stream_status = {
        "status": status,
        "updated_at": datetime.now(tz=UTC).isoformat(),
        **data,
    }
    await event_bus.publish(
        {
            "event": "price.stream.status",
            "occurred_at": latest_price_stream_status["updated_at"],
            "data": latest_price_stream_status,
        }
    )


async def _seed_if_needed() -> None:
    if system.storage.latest_recommendation() is not None:
        return

    async with seed_lock:
        if system.storage.latest_recommendation() is not None:
            return

        cycle = await _run_cycle_with_retries(
            source_timeframe="1m",
            market_context=MarketContext(),
            candles=None,
        )

        payload = {
            "recommendation": cycle.recommendation.model_dump(mode="json"),
            "data_quality_report": cycle.data_quality_report.model_dump(mode="json"),
            "aggregation_counts": cycle.aggregation_counts,
            "generated_at": datetime.now(tz=UTC).isoformat(),
        }
        latest_id = system.storage.latest_recommendation_id()
        if latest_id is not None:
            payload["recommendation"]["id"] = latest_id
        await _publish_cycle_events(payload)


async def _background_live_cycle_runner() -> None:
    while True:
        try:
            _update_background_cycle_status(status="RUNNING", last_started_at=_now_iso())
            if runtime.market_close_pause_enabled:
                hours = market_hours_state(runtime)
                if not hours.is_open:
                    _update_background_cycle_status(status="PAUSED_MARKET_CLOSED")
                    await _publish_worker_event("PAUSED_MARKET_CLOSED", hours)
                    await asyncio.sleep(max(runtime.market_supervisor_interval_seconds, 30))
                    continue
            cycle = await _run_cycle_with_retries(
                source_timeframe="1m",
                market_context=MarketContext(),
                candles=None,
            )
            payload = {
                "recommendation": cycle.recommendation.model_dump(mode="json"),
                "data_quality_report": cycle.data_quality_report.model_dump(mode="json"),
                "aggregation_counts": cycle.aggregation_counts,
                "generated_at": datetime.now(tz=UTC).isoformat(),
            }
            latest_id = system.storage.latest_recommendation_id()
            if latest_id is not None:
                payload["recommendation"]["id"] = latest_id
            await _publish_cycle_events(payload)
            await _auto_execute_if_armed(cycle.recommendation, "background_cycle")
            summary = cycle.recommendation.indicator_summary or {}
            _update_background_cycle_status(
                status="HEALTHY",
                last_success_at=_now_iso(),
                last_error_at=None,
                last_error=None,
                last_signal_time=cycle.recommendation.signal_time.isoformat() if cycle.recommendation.signal_time else None,
                last_session=summary.get("session") or summary.get("session_name") or summary.get("market_session"),
                consecutive_errors=0,
            )
        except Exception as exc:
            details = _record_background_cycle_error(exc)
            await event_bus.publish(
                {
                    "event": "system.error",
                    "occurred_at": datetime.now(tz=UTC).isoformat(),
                    "data": {"message": str(exc), "background_cycle": details},
                }
            )

        await asyncio.sleep(max(runtime.live_cycle_interval_seconds, 5))


async def _start_live_workers() -> None:
    global background_cycle_task, price_stream, price_stream_task, latest_price_stream_status
    if latest_price_stream_status.get("status") in {"MARKET_CLOSED", "SHUTDOWN"}:
        latest_price_stream_status = {
            "status": "CONNECTING",
            "updated_at": datetime.now(tz=UTC).isoformat(),
            "message": "Market is open; live workers are starting.",
        }
    if runtime.enable_background_cycle_runner and (background_cycle_task is None or background_cycle_task.done()):
        background_cycle_task = asyncio.create_task(_background_live_cycle_runner())
        background_cycle_task.add_done_callback(_background_cycle_done)
    if runtime.enable_live_price_stream and price_stream_task is None:
        price_stream = CapitalLivePriceStream(runtime, _publish_price_tick, _publish_price_stream_status)
        price_stream_task = asyncio.create_task(price_stream.stream_forever())


async def _stop_live_workers(reason: str = "STOPPED") -> None:
    global background_cycle_task, price_stream, price_stream_task, latest_price_stream_status
    if background_cycle_task is not None:
        background_cycle_task.cancel()
        with suppress(asyncio.CancelledError):
            await background_cycle_task
        background_cycle_task = None
        _update_background_cycle_status(status=reason)

    if price_stream_task is not None:
        if price_stream is not None:
            with suppress(Exception):
                await price_stream.stop()
        price_stream_task.cancel()
        with suppress(asyncio.CancelledError):
            await price_stream_task
        price_stream_task = None
        price_stream = None

    latest_price_stream_status = {
        "status": reason,
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "message": "Live workers are paused while the market is closed.",
    }


async def _market_supervisor_runner() -> None:
    while True:
        try:
            hours = market_hours_state(runtime)
            if hours.is_open:
                await _start_live_workers()
            else:
                await _stop_live_workers("MARKET_CLOSED")
                await _publish_worker_event("PAUSED_MARKET_CLOSED", hours)
                await _trigger_market_close_backtest(hours)
        except Exception as exc:
            await event_bus.publish(
                {
                    "event": "system.error",
                    "occurred_at": datetime.now(tz=UTC).isoformat(),
                    "data": {"component": "market_supervisor", "message": str(exc)},
                }
            )
        await asyncio.sleep(max(runtime.market_supervisor_interval_seconds, 30))


async def _publish_worker_event(status: str, hours: MarketHoursState) -> None:
    await event_bus.publish(
        {
            "event": "workers.status",
            "occurred_at": datetime.now(tz=UTC).isoformat(),
            "data": {
                "status": status,
                "market_open": hours.is_open,
                "reason": hours.reason,
                "timezone": hours.timezone,
                "next_transition": hours.next_transition.isoformat() if hours.next_transition else None,
                "closure_key": hours.closure_key,
            },
        }
    )


async def _trigger_market_close_backtest(hours: MarketHoursState) -> None:
    global last_market_close_backtest_key, market_close_backtest_task
    if not runtime.market_close_backtest_enabled or not hours.closure_key:
        return
    if last_market_close_backtest_key == hours.closure_key:
        return
    if market_close_backtest_task is not None and not market_close_backtest_task.done():
        return

    run_id = f"AUTO_MARKET_CLOSE_{hours.closure_key}"
    existing = system.storage.get_backtest_run(run_id)
    if existing and existing.get("status") in {"RUNNING", "COMPLETED", "FAILED"}:
        last_market_close_backtest_key = hours.closure_key
        return

    last_market_close_backtest_key = hours.closure_key
    payload = _market_close_backtest_payload(run_id, hours)
    market_close_backtest_task = asyncio.create_task(_run_market_close_backtest(payload))


def _market_close_backtest_payload(run_id: str, hours: MarketHoursState) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_type": "WALK_FORWARD",
        "name": "auto_market_close",
        "instrument": runtime.instrument,
        "timeframe": runtime.cycle_timeframe,
        "synthetic_count": runtime.market_close_backtest_synthetic_count,
        "train_size": runtime.market_close_backtest_train_size,
        "test_size": runtime.market_close_backtest_test_size,
        "step_size": runtime.market_close_backtest_step_size,
        "min_window": runtime.market_close_backtest_min_window,
        "model_mode": "MOCK_FOR_TEST_ONLY",
        "source": "market_close_supervisor",
        "market_close": {
            "closure_key": hours.closure_key,
            "timezone": hours.timezone,
            "weekly_close": hours.weekly_close.isoformat(),
            "next_open": hours.next_transition.isoformat() if hours.next_transition else None,
        },
    }


async def _run_market_close_backtest(payload: dict[str, Any]) -> None:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_backtest_job_sync, payload),
            timeout=max(runtime.market_close_backtest_timeout_seconds, 30),
        )
    except Exception as exc:
        run_id = str(payload.get("run_id") or "AUTO_MARKET_CLOSE")
        system.storage.update_backtest_run(run_id, "FAILED", summary_json={}, error_message=str(exc))
        result = {"run_id": run_id, "status": "FAILED", "message": str(exc)}
    await event_bus.publish(
        {
            "event": "backtest.auto_market_close",
            "occurred_at": datetime.now(tz=UTC).isoformat(),
            "data": result,
        }
    )


def _is_transient_cycle_error(exc: Exception) -> bool:
    transient_types: tuple[type[Exception], ...] = (TimeoutError, ConnectionError, OSError)

    try:
        import requests

        transient_types = transient_types + (requests.RequestException,)  # type: ignore[assignment]
    except Exception:
        pass

    return isinstance(exc, transient_types)


async def _run_cycle_with_retries(
    source_timeframe: str,
    market_context: MarketContext,
    candles: list[dict[str, Any]] | None,
):
    attempts = 1 if candles is not None else max(runtime.live_cycle_retry_attempts, 1)
    backoff = max(runtime.live_cycle_retry_backoff_seconds, 0.1)

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with cycle_execution_lock:
                if candles is not None:
                    return await asyncio.to_thread(
                        system.run_signal_cycle,
                        candles,
                        source_timeframe,
                        market_context,
                    )
                return await asyncio.to_thread(
                    system.run_live_cycle,
                    source_timeframe,
                    market_context,
                )
        except Exception as exc:
            last_exc = exc
            should_retry = attempt < attempts and _is_transient_cycle_error(exc)
            if not should_retry:
                raise
            await asyncio.sleep(backoff * attempt)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Cycle execution failed without exception context")


async def _latest_price_for_execution() -> dict[str, Any]:
    return await get_latest_price()


async def _execute_recommendation(
    signal_id: int,
    recommendation: FinalRecommendation,
    source: str,
) -> dict[str, Any]:
    latest_price_state = await _latest_price_for_execution()
    _execution_control_service()
    async with broker_execution_lock:
        result = await asyncio.to_thread(
            execution_service.execute_recommendation,
            signal_id,
            recommendation,
            source,
            latest_price_state,
        )
    await _publish_execution_event(result)
    return result


async def _auto_execute_if_armed(recommendation: FinalRecommendation, source: str) -> dict[str, Any] | None:
    if not (runtime.capital_execution_enabled and runtime.capital_execution_auto_execute):
        return None
    if not execution_service.should_attempt_auto_execution(recommendation):
        return None
    signal_id = system.storage.latest_recommendation_id()
    if not signal_id:
        return None
    control = _execution_control_service()
    decision = control.evaluate(signal_id, recommendation, source=source, record=False)
    if not decision.allowed:
        control.record_decision(decision)
        result = {
            "status": "BLOCKED_BY_CONTROL_UNIT",
            "message": decision.reason,
            "control_decision": decision.model_dump(mode="json"),
        }
        await _publish_execution_event(result)
        return result
    return await _execute_recommendation(signal_id, recommendation, source)


@app.on_event("startup")
async def startup_event() -> None:
    global market_supervisor_task
    bootstrap_runtime_state(system, optimization_service, runtime)
    if runtime.market_close_pause_enabled:
        if market_supervisor_task is None:
            market_supervisor_task = asyncio.create_task(_market_supervisor_runner())
    else:
        await _start_live_workers()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global market_supervisor_task, market_close_backtest_task
    if market_supervisor_task is not None:
        market_supervisor_task.cancel()
        with suppress(asyncio.CancelledError):
            await market_supervisor_task
        market_supervisor_task = None
    if market_close_backtest_task is not None:
        market_close_backtest_task.cancel()
        with suppress(asyncio.CancelledError):
            await market_close_backtest_task
        market_close_backtest_task = None
    await _stop_live_workers("SHUTDOWN")

    if hasattr(system.storage, "close"):
        with suppress(Exception):
            system.storage.close()


@app.get("/favicon.ico")
async def get_favicon():
    return Response(status_code=204)


@app.get("/api/dashboard/summary")
async def get_dashboard_summary() -> dict[str, Any]:
    await _seed_if_needed()
    return system.dashboard_summary()


@app.get("/api/dashboard/current-signal")
async def get_dashboard_current_signal() -> dict[str, Any]:
    return await get_latest_signal()


@app.get("/api/signals/latest")
async def get_latest_signal() -> dict[str, Any]:
    await _seed_if_needed()
    latest = system.storage.latest_recommendation()
    if latest is None:
        return {}
    payload = latest.model_dump(mode="json")
    latest_id = system.storage.latest_recommendation_id()
    if latest_id is not None:
        payload["id"] = latest_id
    return payload


@app.get("/api/price/latest")
async def get_latest_price() -> dict[str, Any]:
    if latest_price_stream_status.get("status") == "MARKET_CLOSED":
        return {
            "status": "MARKET_CLOSED",
            "instrument": runtime.instrument,
            "epic": runtime.capitalcom_epic,
            "source": "capital.com.websocket",
            "stream": latest_price_stream_status,
            "message": "Market is closed; live price workers are paused.",
        }
    if latest_price_tick is not None:
        return latest_price_tick
    return {
        "status": "DISABLED" if not runtime.enable_live_price_stream else latest_price_stream_status.get("status", "WAITING_FOR_STREAM"),
        "instrument": runtime.instrument,
        "epic": runtime.capitalcom_epic,
        "source": "capital.com.websocket",
        "stream": latest_price_stream_status,
        "message": "Live price websocket is memory-only and waiting for the first tick.",
    }


@app.get("/api/execution/status")
async def get_execution_status() -> dict[str, Any]:
    _execution_control_service()
    return execution_service.status()


@app.get("/api/execution/control")
async def get_execution_control() -> dict[str, Any]:
    service = _execution_control_service()
    current_session = service.session_state_for_time(datetime.now(tz=UTC))
    return {
        "status": "OK",
        "sessions": list(EXECUTION_CONTROL_SESSIONS),
        "session_config": gold_market_session_config(),
        "current_session": current_session["session"],
        "current_session_jordan_time": current_session["jordan_time"],
        "current_session_utc": current_session["utc"],
        "current_session_trading_allowed": current_session["trading_allowed"],
        "config": service.get_config().model_dump(mode="json"),
    }


@app.put("/api/execution/control")
async def update_execution_control(payload: ExecutionControlConfig) -> dict[str, Any]:
    service = _execution_control_service()
    config = service.save_config(payload.model_dump(mode="json"), updated_by="dashboard")
    current_session = service.session_state_for_time(datetime.now(tz=UTC))
    return {
        "status": "OK",
        "sessions": list(EXECUTION_CONTROL_SESSIONS),
        "current_session": current_session["session"],
        "current_session_jordan_time": current_session["jordan_time"],
        "current_session_utc": current_session["utc"],
        "current_session_trading_allowed": current_session["trading_allowed"],
        "config": config.model_dump(mode="json"),
        "statistics": service.statistics(),
    }


@app.get("/api/execution/control/stats")
async def get_execution_control_stats() -> dict[str, Any]:
    return _execution_control_service().statistics()


@app.get("/api/execution/orders")
async def get_execution_orders(
    limit: int = 100,
    page: int = 1,
    page_size: int | None = None,
    status: str | None = None,
    outcome: str | None = None,
    direction: str | None = None,
    market_session: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    signal_id: int | None = None,
    executed_only: bool = True,
) -> dict[str, Any]:
    with suppress(Exception):
        await _refresh_execution_outcomes()
    return system.storage.list_execution_orders(
        limit=limit,
        page=page,
        page_size=page_size,
        status=status,
        outcome=outcome,
        direction=direction,
        market_session=market_session,
        from_time=from_time,
        to_time=to_time,
        signal_id=signal_id,
        executed_only=executed_only,
    )


def _execution_order_full_payload(order: dict[str, Any]) -> dict[str, Any]:
    signal_id = order.get("signal_id")
    signal_detail: dict[str, Any] | None = None
    if signal_id is not None:
        with suppress(Exception):
            signal_detail = system.storage.get_signal_detail(int(signal_id))
    return {
        "execution_order": order,
        "signal_detail": signal_detail,
        "broker_response": order.get("response_json") or {},
        "broker_confirm": order.get("confirm_json") or {},
    }


@app.get("/api/execution/orders/export")
async def export_execution_orders(
    status: str | None = None,
    outcome: str | None = None,
    direction: str | None = None,
    market_session: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    signal_id: int | None = None,
    executed_only: bool = True,
) -> Response:
    with suppress(Exception):
        await _refresh_execution_outcomes()
    result = system.storage.list_execution_orders(
        limit=100000,
        page=1,
        page_size=100000,
        status=status,
        outcome=outcome,
        direction=direction,
        market_session=market_session,
        from_time=from_time,
        to_time=to_time,
        signal_id=signal_id,
        executed_only=executed_only,
    )
    items = [_execution_order_full_payload(order) for order in result.get("items", [])]
    payload = {
        "exported_at": datetime.now(tz=UTC).isoformat(),
        "filters": {
            "status": status,
            "outcome": outcome,
            "direction": direction,
            "market_session": market_session,
            "from_time": from_time.isoformat() if from_time else None,
            "to_time": to_time.isoformat() if to_time else None,
            "signal_id": signal_id,
            "executed_only": executed_only,
        },
        "total": result.get("total", len(items)),
        "statistics": result.get("statistics", {}),
        "items": items,
    }
    filename = f"execution_orders_{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    return Response(
        content=json.dumps(payload, default=str, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _refresh_execution_outcomes() -> dict[str, Any]:
    latest_price_state = await _latest_price_for_execution()
    return await asyncio.to_thread(execution_service.refresh_execution_outcomes, latest_price_state)


@app.post("/api/execution/refresh-outcomes")
async def refresh_execution_outcomes() -> dict[str, Any]:
    result = await _refresh_execution_outcomes()
    await _publish_execution_event({"status": "OUTCOMES_REFRESHED", **result})
    return result


@app.post("/api/execution/execute-latest")
async def execute_latest_signal(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    await _seed_if_needed()
    latest = system.storage.latest_recommendation()
    signal_id = system.storage.latest_recommendation_id()
    if latest is None or signal_id is None:
        return {"status": "ERROR", "message": "No signal is available to execute."}
    source = str((payload or {}).get("source") or "manual_latest")
    return await _execute_recommendation(signal_id, latest, source)


@app.post("/api/execution/execute/{signal_id}")
async def execute_signal(signal_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    recommendation_payload = system.storage.get_signal_detail(signal_id)
    if recommendation_payload is None:
        return {"status": "ERROR", "message": f"Signal {signal_id} was not found."}
    recommendation = FinalRecommendation.model_validate(recommendation_payload)
    source = str((payload or {}).get("source") or "manual_signal")
    return await _execute_recommendation(signal_id, recommendation, source)


@app.get("/api/signals/history")
async def get_signal_history(
    status: str | None = None,
    signal: str | None = None,
    timeframe: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    outcome: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_signal_history(
        status=status,
        signal=signal,
        timeframe=timeframe,
        from_time=from_time,
        to_time=to_time,
        outcome=outcome,
        page=page,
        page_size=page_size,
    )


@app.get("/api/signals/recent")
async def get_recent_signals(page: int = 1, page_size: int = 25) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_signal_history(page=page, page_size=page_size)


@app.get("/api/signals/outcomes")
async def get_signal_outcomes(page: int = 1, page_size: int = 50) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_signal_outcomes(page=page, page_size=page_size)


@app.get("/api/signals/outcomes/summary")
async def get_signal_outcome_summary() -> dict[str, Any]:
    outcomes = system.storage.get_signal_outcomes(page=1, page_size=1000).get("items", [])
    counts: dict[str, int] = {}
    for item in outcomes:
        outcome = str(item.get("outcome", "UNKNOWN"))
        counts[outcome] = counts.get(outcome, 0) + 1
    return {"total": len(outcomes), "counts": counts}


async def _validate_pending_signals(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    timeframe = payload.get("source_timeframe", "1m")
    candles = system.candle_provider.fetch_latest_candles(
        instrument=system.runtime.instrument,
        timeframe=timeframe,
        limit=system.runtime.live_candle_lookback,
    )
    cycle = system.run_signal_cycle(
        raw_candles=candles,
        source_timeframe=timeframe,
        market_context=MarketContext(**(payload.get("market_context") or {})),
    )
    return {
        "status": "OK",
        "recommendation": cycle.recommendation.model_dump(mode="json"),
        "outcomes": system.storage.get_signal_outcomes(page=1, page_size=50),
    }


@app.post("/api/signals/validate-outcomes")
async def validate_signal_outcomes(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return await _validate_pending_signals(payload)


@app.post("/api/signals/validate-pending")
async def validate_pending_signals(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return await _validate_pending_signals(payload)


@app.get("/api/signals/{signal_id}")
async def get_signal_detail(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    detail = system.storage.get_signal_detail(signal_id)
    if detail is None:
        return {}
    return detail


@app.get("/api/signals/{signal_id}/snapshot")
async def get_signal_snapshot(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    snapshot = system.storage.get_signal_snapshot(signal_id)
    if snapshot is None:
        return {}
    return snapshot


@app.get("/api/signals/{signal_id}/outcome")
async def get_signal_outcome(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    outcome = system.storage.get_signal_outcome(signal_id)
    if outcome is None:
        return {"recommendation_id": signal_id, "outcome": "PENDING", "message": "Pending validation"}
    return outcome


@app.get("/api/signals/{signal_id}/regime")
async def get_signal_regime(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_signal_regime(signal_id)


@app.get("/api/signals/{signal_id}/timeframe-confirmation")
async def get_signal_timeframe_confirmation(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_signal_timeframe_confirmation(signal_id)


@app.get("/api/signals/{signal_id}/entry-plans")
async def get_signal_entry_plans(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_signal_entry_plans(signal_id)


@app.get("/api/signals/{signal_id}/selected-plan")
async def get_signal_selected_plan(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.get_selected_entry_plan(signal_id)


@app.get("/api/signals/{signal_id}/replay")
async def get_signal_replay(signal_id: int) -> dict[str, Any]:
    await _seed_if_needed()
    return replay_service.build_replay(system.storage, signal_id)


@app.get("/api/models/latest-votes")
async def get_latest_model_votes(timeframe: str | None = None) -> list[dict[str, Any]]:
    await _seed_if_needed()
    return [p.model_dump(mode="json") for p in system.storage.latest_model_votes(timeframe)]


@app.get("/api/models/artifacts")
async def get_model_artifacts() -> dict[str, Any]:
    return {
        "artifact_dir": system.runtime.model_artifacts_dir,
        "models": system.model_engine.artifact_status,
    }


@app.get("/api/models/performance")
async def get_model_performance() -> dict[str, Any]:
    return {
        "metrics": system.performance_tracker.metrics(),
        "dynamic_model_weights": system.model_engine.model_weights.weights,
        "last_updated_at": (
            system.performance_tracker.last_updated_at.isoformat()
            if system.performance_tracker.last_updated_at
            else None
        ),
    }


@app.get("/api/models/performance/summary")
async def get_model_performance_summary() -> dict[str, Any]:
    metrics = system.performance_tracker.metrics()
    return {
        "models": metrics,
        "model_signal_predictions": len(system.storage.model_signal_predictions),
        "model_prediction_outcomes": len(system.storage.model_prediction_outcomes),
        "last_updated_at": (
            system.performance_tracker.last_updated_at.isoformat()
            if system.performance_tracker.last_updated_at
            else None
        ),
    }


@app.get("/api/models/performance/by-regime")
async def get_model_performance_by_regime() -> dict[str, Any]:
    return system.performance_tracker.by_regime()


@app.get("/api/models/performance/confidence-calibration")
async def get_model_confidence_calibration() -> dict[str, Any]:
    return system.performance_tracker.confidence_calibration()


@app.get("/api/models/performance/{model_name}")
async def get_model_performance_detail(model_name: str) -> dict[str, Any]:
    return system.performance_tracker.model_metrics(model_name)


@app.get("/api/models/weights/current")
async def get_current_model_weights() -> dict[str, Any]:
    persisted = system.storage.load_model_weight_state()
    return {
        "effective_weights": system.model_engine.model_weights.weights,
        "details": system.dynamic_weight_service.current_weights(),
        "persistent_profile": persisted or {"status": "DEFAULT_WEIGHTS", "message": "Using default model weights. No adaptive updates yet."},
    }


@app.get("/api/models/weights/history")
async def get_model_weight_history() -> dict[str, Any]:
    persisted = system.storage.load_model_weight_state()
    versions = persisted.get("versions") if isinstance(persisted, dict) else None
    items = [item.model_dump() for item in system.dynamic_weight_service.history[-200:]]
    return {"items": items, "versions": versions or [], "message": "Using default model weights. No adaptive updates yet." if not items and not versions else None}


@app.post("/api/models/weights/recalculate")
async def recalculate_model_weights() -> dict[str, Any]:
    votes = system.storage.latest_model_votes(timeframe)
    results = system.dynamic_weight_service.calculate(
        base_weights=system.configured_model_weights.weights,
        predictions=votes,
        metrics=system.performance_tracker.metrics(),
        market_regime=system.storage.latest_market_regime().get("primary_regime", "UNKNOWN"),
        session=(system.storage.latest_indicator_snapshot(timeframe).session_name if system.storage.latest_indicator_snapshot(timeframe) else "UNKNOWN"),
    )
    system.model_engine.model_weights = ModelWeights(weights={item.model_name: item.effective_weight for item in results})
    system.storage.save_model_weight_state(
        weights={item.model_name: item.effective_weight for item in results},
        history=[item.model_dump() for item in results],
        profile_versions=list(system.dynamic_weight_service.profile_versions[-1:]),
        reason="manual_recalculate",
    )
    return {"status": "OK", "weights": {item.model_name: item.model_dump() for item in results}}


@app.put("/api/models/weights/profile/{model_name}")
async def update_model_weight_profile(model_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    from .dynamic_weights import ModelWeightProfile

    profile = ModelWeightProfile(
        model_name=model_name.lower(),
        base_weight=float(payload.get("base_weight", system.model_engine.model_weights.weights.get(model_name.lower(), 0.0))),
        min_weight=float(payload.get("min_weight", 0.01)),
        max_weight=float(payload.get("max_weight", 0.60)),
        is_enabled=bool(payload.get("is_enabled", True)),
        applies_to_timeframe=str(payload.get("applies_to_timeframe", "*")),
    )
    system.dynamic_weight_service.set_profile(model_name, profile)
    system.storage.save_model_weight_state(
        weights=dict(system.model_engine.model_weights.weights),
        history=[],
        profile_versions=list(system.dynamic_weight_service.profile_versions[-1:]),
        reason=f"profile_update:{model_name.lower()}",
    )
    return {"status": "OK", "profile": profile.__dict__}


@app.get("/api/market/regime/current")
async def get_current_market_regime(timeframe: str | None = None) -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.latest_market_regime(timeframe)


@app.get("/api/market/regime/history")
async def get_market_regime_history() -> dict[str, Any]:
    return {"items": system.storage.market_regimes[-100:]}


@app.get("/api/market/hours")
async def get_market_hours() -> dict[str, Any]:
    state = market_hours_state(runtime)
    return {
        "market_open": state.is_open,
        "timezone": state.timezone,
        "reason": state.reason,
        "now": state.now.isoformat(),
        "weekly_open": state.weekly_open.isoformat(),
        "weekly_close": state.weekly_close.isoformat(),
        "next_transition": state.next_transition.isoformat() if state.next_transition else None,
        "closure_key": state.closure_key,
        "pause_enabled": runtime.market_close_pause_enabled,
        "auto_backtest_enabled": runtime.market_close_backtest_enabled,
    }


@app.get("/api/market/timeframes/current")
async def get_current_timeframe_confirmation() -> dict[str, Any]:
    await _seed_if_needed()
    return system.storage.latest_timeframe_confirmation()


@app.get("/api/news/upcoming")
async def get_upcoming_news(hours: int = 24) -> dict[str, Any]:
    return {"items": system.news_filter.upcoming(hours=hours)}


@app.get("/api/news/current-risk")
async def get_current_news_risk() -> dict[str, Any]:
    payload = system.news_filter.current_risk().model_dump()
    payload["provider_mode"] = system.news_filter.mode
    payload["provider_status"] = system.news_filter.last_sync_status
    return payload


@app.post("/api/news/sync")
async def sync_news(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    for item in payload.get("events", []):
        scheduled = item.get("scheduled_at")
        if not scheduled:
            continue
        try:
            event = EconomicNewsEvent(
                source=str(item.get("source", "manual")),
                event_name=str(item.get("event_name", item.get("name", "Unknown event"))),
                country=str(item.get("country", "US")),
                currency=str(item.get("currency", "USD")),
                impact=str(item.get("impact", "HIGH")),
                scheduled_at=parser.isoparse(str(scheduled)),
                actual=item.get("actual"),
                forecast=item.get("forecast"),
                previous=item.get("previous"),
                status=str(item.get("status", "SCHEDULED")),
            )
            system.news_filter.provider.add_event(event)
        except Exception:
            continue
    result = system.news_filter.sync()
    system.health_service.last_news_sync_status = result["status"]
    return result


@app.get("/api/indicators/latest")
async def get_latest_indicators(timeframe: str | None = None) -> dict[str, Any]:
    await _seed_if_needed()
    snapshot = system.storage.latest_indicator_snapshot(timeframe)
    if snapshot is None:
        return {}
    return snapshot.model_dump(mode="json")


@app.get("/api/risk/status")
async def get_risk_status(timeframe: str | None = None) -> dict[str, Any]:
    await _seed_if_needed()
    risk = system.storage.latest_risk_check(timeframe)
    if risk is None:
        return {"risk_status": "UNKNOWN"}
    return risk.model_dump(mode="json")


@app.get("/api/backtest/summary")
async def get_backtest_summary() -> dict[str, Any]:
    return system.storage.latest_backtest_summary()


@app.get("/api/backtest/status")
async def get_backtest_status() -> dict[str, Any]:
    runs = system.storage.list_backtest_runs(limit=20).get("items", [])
    active = next((item for item in runs if item.get("status") == "RUNNING"), None)
    latest = active or (runs[0] if runs else None)
    if latest is None:
        return {"status": "IDLE", "message": "No backtest has been started.", "active": False, "progress": 0}
    detail = system.storage.get_backtest_run(str(latest.get("run_id"))) or latest
    progress = _estimate_backtest_progress(detail)
    return {
        **detail,
        "active": detail.get("status") == "RUNNING",
        "progress": progress,
        "elapsed_seconds": _elapsed_seconds(detail.get("started_at"), detail.get("completed_at")),
        "message": _backtest_status_message(detail, progress),
    }


def _estimate_backtest_progress(run: dict[str, Any]) -> int:
    status = str(run.get("status") or "").upper()
    if status == "COMPLETED":
        return 100
    if status in {"FAILED", "CANCELLED", "INTERRUPTED"}:
        return 100
    if status != "RUNNING":
        return 0
    config = run.get("config") or run.get("config_json") or {}
    synthetic_count = int(config.get("synthetic_count") or runtime.market_close_backtest_synthetic_count or 120)
    train_size = int(config.get("train_size") or runtime.market_close_backtest_train_size or 90)
    test_size = int(config.get("test_size") or runtime.market_close_backtest_test_size or 20)
    step_size = int(config.get("step_size") or runtime.market_close_backtest_step_size or test_size or 20)
    expected_windows = max(1, ((max(synthetic_count - train_size - test_size, 0)) // max(step_size, 1)) + 1)
    folds = system.storage.get_walk_forward_folds(str(run.get("run_id"))).get("total", 0)
    if folds:
        return min(95, max(5, int((folds / expected_windows) * 95)))
    elapsed = _elapsed_seconds(run.get("started_at"), None) or 0
    timeout = max(runtime.market_close_backtest_timeout_seconds, 30)
    return min(90, max(5, int((elapsed / timeout) * 90)))


def _elapsed_seconds(started_at: Any, completed_at: Any | None = None) -> int | None:
    if not started_at:
        return None
    try:
        start = parser.isoparse(str(started_at)) if isinstance(started_at, str) else started_at
        end = parser.isoparse(str(completed_at)) if isinstance(completed_at, str) else completed_at
        end = end or datetime.now(tz=UTC)
        return max(0, int((end.astimezone(UTC) - start.astimezone(UTC)).total_seconds()))
    except Exception:
        return None


def _backtest_status_message(run: dict[str, Any], progress: int) -> str:
    status = str(run.get("status") or "UNKNOWN").upper()
    run_id = run.get("run_id") or "backtest"
    if status == "RUNNING":
        return f"{run_id} is running ({progress}%)."
    if status == "COMPLETED":
        return f"{run_id} completed."
    if status in {"FAILED", "INTERRUPTED", "CANCELLED"}:
        return f"{run_id} {status.lower()}: {run.get('error_message') or 'No error message.'}"
    return f"{run_id} status is {status}."


def _candles_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    payload = payload or {}
    candles = payload.get("candles")
    if isinstance(candles, list) and candles:
        return candles
    return generate_synthetic_candles(count=int(payload.get("synthetic_count", 420)), timeframe=payload.get("timeframe", "1m"))


def _next_backtest_run_id(run_type: str) -> str:
    prefix = "WF" if run_type == "WALK_FORWARD" else "BT"
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    existing = system.storage.list_backtest_runs(limit=1000).get("total", 0)
    return f"{prefix}-{stamp}-{int(existing) + 1:03d}"


def _report_files(report_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(report_dir)
    if not path.exists():
        return []
    return [
        {"report_type": file.stem, "report_path": str(file), "metadata_json": {"size": file.stat().st_size}}
        for file in sorted(path.iterdir())
        if file.is_file()
    ]


def _write_normal_backtest_reports(run_id: str, report: dict[str, Any], trades: list[dict[str, Any]], config: dict[str, Any]) -> Path:
    report_dir = Path(runtime.reports_dir) / "backtests" / run_id
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = {key: value for key, value in report.items() if key != "trade_simulation"}
    summary.update(
        {
            "run_id": run_id,
            "run_type": "BACKTEST",
            "instrument": config.get("instrument", runtime.instrument),
            "timeframe": config.get("timeframe", runtime.cycle_timeframe),
            "status": "COMPLETED",
            "model_mode": config.get("model_mode", "MOCK_FOR_TEST_ONLY"),
        }
    )
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (report_dir / "metrics.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    fieldnames = sorted({key for trade in trades for key in trade.keys()}) if trades else ["time", "signal", "outcome", "realized_rr"]
    with (report_dir / "trades.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)

    (report_dir / "recommendations.md").write_text(
        "# Backtest Recommendations\n\n"
        "- Compare this run with walk-forward validation before changing production thresholds.\n"
        "- Confirm the model mode before trusting the result for live deployment.\n",
        encoding="utf-8",
    )
    return report_dir


def _persist_walk_forward_run(run_id: str, run: dict[str, Any], window_reports: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
    config = dict(run.get("config") or {})
    summary = dict(run.get("summary") or {})
    summary.update(
        {
            "run_id": run_id,
            "run_type": "WALK_FORWARD",
            "instrument": run.get("instrument", runtime.instrument),
            "timeframe": run.get("timeframe", config.get("timeframe", runtime.cycle_timeframe)),
            "status": "COMPLETED",
            "model_mode": config.get("model_mode", "MOCK_FOR_TEST_ONLY"),
        }
    )
    report_path = run.get("report_path") or str(Path(run.get("report_dir", "")) / "summary.json")
    system.storage.update_backtest_run(run_id, "COMPLETED", summary_json=summary, report_path=report_path)
    system.storage.save_backtest_trades(run_id, trades)
    system.storage.save_backtest_metrics(run_id, summary)
    system.storage.save_walk_forward_run(
        run_id=run_id,
        instrument=str(run.get("instrument", runtime.instrument)),
        timeframe=str(run.get("timeframe", config.get("timeframe", runtime.cycle_timeframe))),
        status="COMPLETED",
        config_json=config,
        summary_json=summary,
        report_path=report_path,
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
    )
    system.storage.save_walk_forward_folds(run_id, window_reports)
    system.storage.save_walk_forward_reports(run_id, _report_files(run.get("report_dir", "")))
    return system.storage.get_backtest_run(run_id) or {}


def _run_backtest_job_sync(payload: dict[str, Any]) -> dict[str, Any]:
    run_type = str(payload.get("run_type", "WALK_FORWARD")).upper()
    if run_type not in {"BACKTEST", "WALK_FORWARD"}:
        run_type = "WALK_FORWARD"

    instrument = str(payload.get("instrument", runtime.instrument))
    timeframe = str(payload.get("timeframe", runtime.cycle_timeframe))
    model_mode = str(payload.get("model_mode") or ("MOCK_FOR_TEST_ONLY" if "candles" not in payload else "LIVE_INFERENCE"))
    run_id = str(payload.get("run_id") or _next_backtest_run_id(run_type))
    config_json = {
        "run_type": run_type,
        "instrument": instrument,
        "timeframe": timeframe,
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "initial_balance": float(payload.get("initial_balance", 10000) or 10000),
        "risk_percent": float(payload.get("risk_percent", 1.0) or 1.0),
        "strategy_version": payload.get("strategy_version", runtime.strategy_version),
        "threshold_profile": payload.get("threshold_profile", runtime.threshold_profile_name),
        "model_weight_profile": payload.get("model_weight_profile", "active"),
        "model_mode": model_mode,
        "synthetic_count": int(payload.get("synthetic_count", 260) or 260),
    }
    system.storage.create_backtest_run(run_id, run_type, instrument, timeframe, config_json, status="RUNNING")

    try:
        candles = _candles_from_payload({**payload, "timeframe": timeframe, "instrument": instrument, "synthetic_count": config_json["synthetic_count"]})
        if run_type == "WALK_FORWARD":
            wf_config = WalkForwardConfig(
                train_size=int(payload.get("train_size", payload.get("config", {}).get("train_size", 90))),
                test_size=int(payload.get("test_size", payload.get("config", {}).get("test_size", 50))),
                step_size=int(payload.get("step_size", payload.get("config", {}).get("step_size", 50))),
                min_window=int(payload.get("min_window", payload.get("config", {}).get("min_window", 80))),
                instrument=instrument,
                timeframe=timeframe,
                model_mode=model_mode,
                threshold_config={"profile": config_json["threshold_profile"]},
            )
            run = walk_forward_service.run(candles, config=wf_config, name=str(payload.get("name", "dashboard_walk_forward")), run_id=run_id)
            windows = walk_forward_service.windows.get(run_id, [])
            trades = walk_forward_service.signals.get(run_id, [])
            result = _persist_walk_forward_run(run_id, run, windows, trades)
            return {"run_id": run_id, "status": "COMPLETED", "message": "Walk-forward backtest completed.", "result": result}

        min_window = int(payload.get("min_window", 80))
        report = BacktestingEngine(system, BacktestConfig(min_window=min_window)).run(candles, source_timeframe=timeframe)
        trades = list(report.get("trade_simulation", []))
        report_dir = _write_normal_backtest_reports(run_id, report, trades, config_json)
        summary = {key: value for key, value in report.items() if key != "trade_simulation"}
        summary.update(
            {
                "run_id": run_id,
                "run_type": "BACKTEST",
                "instrument": instrument,
                "timeframe": timeframe,
                "status": "COMPLETED",
                "model_mode": model_mode,
            }
        )
        report_path = str(report_dir / "summary.json")
        system.storage.update_backtest_run(run_id, "COMPLETED", summary_json=summary, report_path=report_path)
        system.storage.save_backtest_trades(run_id, trades)
        system.storage.save_backtest_metrics(run_id, summary)
        result = system.storage.get_backtest_run(run_id) or {}
        return {"run_id": run_id, "status": "COMPLETED", "message": "Backtest completed.", "result": result}
    except Exception as exc:
        system.storage.update_backtest_run(run_id, "FAILED", summary_json={}, error_message=str(exc))
        return {"run_id": run_id, "status": "FAILED", "message": str(exc)}


@app.post("/api/backtests/run")
async def run_backtest(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return await asyncio.to_thread(_run_backtest_job_sync, payload)


@app.post("/api/backtests/walk-forward/start")
async def start_walk_forward_backtest(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    config_payload = payload.get("config") or {}
    translated = {
        **payload,
        **config_payload,
        "run_type": "WALK_FORWARD",
        "name": payload.get("name", "walk_forward"),
    }
    return await run_backtest(translated)


@app.get("/api/backtests")
async def list_walk_forward_backtests() -> dict[str, Any]:
    return system.storage.list_backtest_runs()


@app.get("/api/backtests/{run_id}")
async def get_walk_forward_backtest(run_id: str) -> dict[str, Any]:
    return system.storage.get_backtest_run(run_id) or {}


@app.get("/api/backtests/{run_id}/windows")
async def get_walk_forward_windows(run_id: str) -> dict[str, Any]:
    return system.storage.get_walk_forward_folds(run_id)


@app.get("/api/backtests/{run_id}/signals")
async def get_walk_forward_signals(run_id: str) -> dict[str, Any]:
    return system.storage.get_backtest_trades(run_id)


@app.get("/api/backtests/{run_id}/trades")
async def get_backtest_trades(run_id: str) -> dict[str, Any]:
    return system.storage.get_backtest_trades(run_id)


@app.post("/api/optimization/start")
async def start_threshold_optimization(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return optimization_service.start(_candles_from_payload(payload), payload.get("search_space"))


@app.get("/api/optimization/runs")
async def get_optimization_runs() -> dict[str, Any]:
    return system.storage.list_optimization_runs()


@app.get("/api/optimization/runs/{run_id}")
async def get_optimization_run(run_id: int) -> dict[str, Any]:
    return system.storage.get_optimization_run(run_id) or {}


@app.get("/api/optimization/runs/{run_id}/candidates")
async def get_optimization_candidates(run_id: int) -> dict[str, Any]:
    return system.storage.get_optimization_candidates(run_id)


@app.get("/api/strategy/profiles/active")
async def get_active_strategy_profile() -> dict[str, Any]:
    return optimization_service.active_profile()


@app.post("/api/strategy/profiles/{profile_id}/activate")
async def activate_strategy_profile(profile_id: int) -> dict[str, Any]:
    result = optimization_service.activate(profile_id)
    active = result.get("active_profile")
    if isinstance(active, dict):
        params = active.get("parameters") or {}
        system.threshold_profile = StrategyThresholdProfile(
            profile_id=int(active.get("id", profile_id)),
            version=int(active.get("version", 1)),
            name=str(active.get("name", "optimized")),
            minimum_final_confidence=float(params.get("minimum_final_confidence", runtime.minimum_final_confidence)),
            minimum_risk_reward=float(params.get("minimum_risk_reward", runtime.minimum_risk_reward)),
            raw=params,
        )
        system.strategy_brain.set_threshold_profile(system.threshold_profile)
    return result


@app.post("/api/strategy/profiles/rollback")
async def rollback_strategy_profile() -> dict[str, Any]:
    result = optimization_service.rollback()
    active = result.get("active_profile")
    if isinstance(active, dict):
        params = active.get("parameters") or {}
        system.threshold_profile = StrategyThresholdProfile(
            profile_id=int(active.get("id", 1)),
            version=int(active.get("version", 1)),
            name=str(active.get("name", "rollback")),
            minimum_final_confidence=float(params.get("minimum_final_confidence", runtime.minimum_final_confidence)),
            minimum_risk_reward=float(params.get("minimum_risk_reward", runtime.minimum_risk_reward)),
            raw=params,
        )
        system.strategy_brain.set_threshold_profile(system.threshold_profile)
    return result


@app.get("/api/system/health")
async def get_system_health() -> dict[str, Any]:
    await _seed_if_needed()
    candles = system.candle_store.get(runtime.instrument, runtime.cycle_timeframe, limit=300)
    health = system.health_service.check(candles, runtime.cycle_timeframe)
    background_health = _background_cycle_health()
    health.setdefault("details", {})["background_cycle"] = background_health
    health["background_cycle"] = background_health
    health["categories"] = {
        "data_feed": health["overall_status"] if health.get("last_candle_time") else "CRITICAL",
        "background_cycle": "HEALTHY" if background_health.get("healthy") else str(background_health.get("status") or "UNKNOWN"),
        "models": "WARNING" if system.health_service.model_failures else "HEALTHY",
        "strategy": "HEALTHY",
        "database": "HEALTHY" if system.storage_backend == "postgresql" else "WARNING",
        "news_provider": "WARNING" if system.news_filter.last_sync_status == "ERROR" else "HEALTHY",
        "backtest_jobs": "HEALTHY",
        "optimization_jobs": "HEALTHY",
        "notifications": "UNKNOWN",
    }
    health["persisted_snapshot"] = system.storage.get_latest_health_snapshot() or {
        "status": "UNAVAILABLE",
        "message": "No persisted health snapshot yet. Runtime health will appear after system starts collecting metrics.",
    }
    return health


@app.get("/api/system/health/events")
async def get_system_health_events() -> dict[str, Any]:
    persisted = system.storage.get_health_events()
    if persisted.get("items"):
        return persisted
    return system.health_service.events_payload()


@app.post("/api/system/health/check-now")
async def check_system_health_now() -> dict[str, Any]:
    return await get_system_health()


@app.post("/api/settings/model-weights")
async def set_model_weights(weights: dict[str, float]) -> dict[str, Any]:
    cleaned = {str(key).lower(): float(value) for key, value in weights.items()}
    total = sum(cleaned.values())
    if not cleaned or total <= 0:
        return {"status": "ERROR", "message": "Model weights must contain positive numeric values."}
    if max(cleaned.values()) > runtime.model_weight_max:
        return {"status": "ERROR", "message": f"No model weight may exceed {runtime.model_weight_max}."}
    normalized = {key: round(value / total, 8) for key, value in cleaned.items()}
    system.configured_model_weights = ModelWeights(weights=normalized)
    system.model_engine.model_weights = ModelWeights(weights=normalized)
    system.dynamic_weight_service._last_effective_weights = {}
    setting = system.storage.save_setting(
        "model_weights.active",
        normalized,
        setting_group="model_weights",
        updated_by="dashboard",
        source="dashboard",
    )
    system.storage.save_model_weight_state(normalized, reason="dashboard_setting_saved")
    return {"status": "OK", "model_weights": normalized, "updated_at": setting.get("updated_at"), "source": setting.get("source", "dashboard")}


@app.post("/api/settings/risk-limits")
async def set_risk_limits(limits: dict[str, Any]) -> dict[str, Any]:
    current = RiskLimits()
    for key, value in limits.items():
        if hasattr(current, key):
            setattr(current, key, value)
    if current.max_spread <= 0 or current.max_risk_per_trade_pct <= 0:
        return {"status": "ERROR", "message": "Risk limits must be positive."}
    system.risk_engine = system.risk_engine.__class__(current)
    clean_limits = {key: value for key, value in limits.items() if hasattr(current, key)}
    setting = system.storage.save_setting(
        "risk_limits.active",
        clean_limits,
        setting_group="risk_limits",
        updated_by="dashboard",
        source="dashboard",
    )
    return {"status": "OK", "risk_limits": clean_limits, "updated_at": setting.get("updated_at"), "source": setting.get("source", "dashboard")}


@app.post("/api/signals/run")
async def run_signal_cycle(payload: dict[str, Any]) -> dict[str, Any]:
    candles = payload.get("candles")
    timeframe = payload.get("source_timeframe", "1m")
    context = payload.get("market_context", {})

    market_context = MarketContext(**context)
    if candles:
        result = await _run_cycle_with_retries(
            source_timeframe=timeframe,
            market_context=market_context,
            candles=candles,
        )
    else:
        result = await _run_cycle_with_retries(
            source_timeframe=timeframe,
            market_context=market_context,
            candles=None,
        )

    response = {
        "recommendation": result.recommendation.model_dump(mode="json"),
        "data_quality_report": result.data_quality_report.model_dump(mode="json"),
        "aggregation_counts": result.aggregation_counts,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }
    latest_id = system.storage.latest_recommendation_id()
    if latest_id is not None:
        response["recommendation"]["id"] = latest_id
    await _publish_cycle_events(response)
    execution_result = await _auto_execute_if_armed(result.recommendation, "manual_cycle")
    if execution_result:
        response["execution"] = execution_result
    return response


@app.post("/api/paper/outcome")
async def ingest_paper_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    recommendation_id = int(payload.get("recommendation_id", 0) or 0)
    if recommendation_id <= 0:
        return {"status": "ERROR", "message": "recommendation_id must be provided"}

    outcome_payload = payload.get("outcome") or {}
    closed_at_raw = outcome_payload.get("closed_at")
    if closed_at_raw:
        try:
            closed_at = parser.isoparse(str(closed_at_raw))
        except Exception:
            closed_at = datetime.now(tz=UTC)
    else:
        closed_at = datetime.now(tz=UTC)

    signal_outcome = SignalOutcome(
        recommendation_id=recommendation_id,
        outcome=str(outcome_payload.get("outcome", "UNKNOWN")),
        entry_triggered=bool(outcome_payload.get("entry_triggered", True)),
        hit_tp1=bool(outcome_payload.get("hit_tp1", False)),
        hit_tp2=bool(outcome_payload.get("hit_tp2", False)),
        hit_tp3=bool(outcome_payload.get("hit_tp3", False)),
        hit_sl=bool(outcome_payload.get("hit_sl", False)),
        max_favorable_move=float(outcome_payload.get("max_favorable_move", 0.0) or 0.0),
        max_adverse_move=float(outcome_payload.get("max_adverse_move", 0.0) or 0.0),
        realized_rr=float(outcome_payload.get("realized_rr", 0.0) or 0.0),
        closed_at=closed_at,
        raw_json={
            "source": "paper_api",
            "payload": outcome_payload,
            "ingested_at": datetime.now(tz=UTC).isoformat(),
        },
    )
    system.storage.save_outcome(signal_outcome)

    recommendation_payload = system.storage.get_signal_detail(recommendation_id)
    if recommendation_payload is None:
        return {
            "status": "WARNING",
            "message": "Outcome saved, but recommendation was not found for performance update",
        }

    recommendation = FinalRecommendation.model_validate(recommendation_payload)
    recommendation.outcome_status = signal_outcome.outcome
    recommendation.entry_triggered = signal_outcome.entry_triggered
    recommendation.realized_rr = signal_outcome.realized_rr
    recommendation.max_favorable_move = signal_outcome.max_favorable_move
    recommendation.max_adverse_move = signal_outcome.max_adverse_move
    recommendation.outcome_validated_at = signal_outcome.closed_at
    system.storage.update_recommendation(recommendation_id, recommendation)
    update = system.record_model_outcome(
        recommendation=recommendation,
        realized_rr=signal_outcome.realized_rr,
        outcome=signal_outcome.outcome,
        source="paper",
    )
    return {
        "status": "OK",
        "recommendation_id": recommendation_id,
        "dynamic_model_weights": update["weights"],
        "updated_at": update["updated_at"],
    }


@app.websocket("/ws/events")
async def events_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await event_bus.subscribe()
    try:
        async for event in event_bus.stream(queue, runtime.websocket_heartbeat_seconds):
            if "occurred_at" not in event:
                event["occurred_at"] = datetime.now(tz=UTC).isoformat()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
    finally:
        await event_bus.unsubscribe(queue)


@app.get("/api/report-file")
def get_report_file(path: str):
    requested = Path(path)
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    reports_root = (Path.cwd() / runtime.reports_dir).resolve()
    resolved = requested.resolve()
    if reports_root not in resolved.parents and resolved != reports_root:
        return {"status": "ERROR", "message": "Report path is outside the configured reports directory."}
    if not resolved.exists() or not resolved.is_file():
        return {"status": "ERROR", "message": "Report file was not found."}
    return FileResponse(str(resolved))


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse("src/gold_signal_system/dashboard_static/index.html")

@app.get("/news")
def news_dashboard() -> FileResponse:
    return FileResponse("src/gold_signal_system/dashboard_static/news.html")

# --- News Intelligence Endpoints ---

@app.get("/api/news/dashboard/summary")
async def get_news_dashboard_summary(instrument: str | None = None) -> dict[str, Any]:
    return system.news_intelligence_service.dashboard_summary(instrument or system.runtime.instrument)


@app.get("/api/news/items")
async def get_news_items(
    instrument: str | None = None,
    limit: int = 50,
    event_type: str | None = None,
    relevance: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    inst = (instrument or system.runtime.instrument).upper()
    return {
        "items": system.news_repository.get_news_items(
            inst,
            limit=limit,
            event_type=event_type,
            relevance=relevance,
            source=source,
        )
    }


@app.get("/api/news/analysis")
async def get_news_analysis(instrument: str | None = None, limit: int = 50, active_only: bool = False) -> dict[str, Any]:
    inst = (instrument or system.runtime.instrument).upper()
    return {"items": system.news_repository.get_ai_analyses(inst, limit=limit, active_only=active_only)}


@app.get("/api/news/state")
async def get_news_state(instrument: str | None = None) -> dict[str, Any]:
    inst = (instrument or system.runtime.instrument).upper()
    state = system.news_repository.get_active_strategy_news_state(inst)
    return state or {}


@app.get("/api/news/active-state")
async def get_active_news_state() -> dict[str, Any]:
    return await get_news_state(system.runtime.instrument)


@app.get("/api/news/macro-events")
async def get_macro_events(
    limit: int = 50,
    event_type: str | None = None,
    type: str | None = None,
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
) -> dict[str, Any]:
    start = parser.isoparse(from_) if from_ else None
    end = parser.isoparse(to) if to else None
    return {
        "items": system.news_repository.get_macro_events(
            start=start,
            end=end,
            event_type=event_type or type,
            limit=limit,
        )
    }


@app.get("/api/news/risk-window")
async def get_news_risk_window(instrument: str | None = None) -> dict[str, Any]:
    return system.news_intelligence_service.risk_window(instrument or system.runtime.instrument)


@app.get("/api/news/sources/health")
async def get_news_sources_health() -> dict[str, Any]:
    return {"sources": system.news_repository.get_source_health()}


@app.post("/api/news/collect/run-now")
async def run_news_collection(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    return await system.news_intelligence_service.collect_run_now(payload.get("instrument") or system.runtime.instrument)


@app.post("/api/news/manual")
async def create_manual_news(payload: dict[str, Any]) -> dict[str, Any]:
    return system.news_intelligence_service.manual_news(payload)


@app.post("/api/news/macro-events/manual")
async def create_manual_macro_event(payload: dict[str, Any]) -> dict[str, Any]:
    MacroEventModel.model_validate(payload)
    return system.news_intelligence_service.manual_macro_event(payload)


@app.put("/api/news/macro-events/{event_id}/actual")
async def update_macro_event_actual(event_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return system.news_intelligence_service.update_macro_actual(event_id, payload)


@app.get("/api/news/validation/summary")
async def get_news_validation_summary(instrument: str | None = None) -> dict[str, Any]:
    return system.news_repository.validation_summary((instrument or system.runtime.instrument).upper())
