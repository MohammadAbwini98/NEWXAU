from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

os.environ.setdefault("ENABLE_BACKGROUND_CYCLE_RUNNER", "0")
os.environ.setdefault("ENABLE_LIVE_PRICE_STREAM", "0")
os.environ.setdefault("CAPITAL_EXECUTION_ENABLED", "0")
os.environ.setdefault("CAPITAL_EXECUTION_AUTO_EXECUTE", "0")
os.environ.setdefault("CAPITAL_EXECUTION_DEMO_ONLY", "1")

from gold_signal_system import api as api_module
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.desktop_runtime import resolve_resource_path, resolve_runtime_path


def _safe_runtime(monkeypatch, token: str = "desktop-test-token") -> None:
    monkeypatch.setattr(api_module, "desktop_token", token)
    monkeypatch.setattr(api_module.runtime, "enable_background_cycle_runner", False)
    monkeypatch.setattr(api_module.runtime, "enable_live_price_stream", False)
    monkeypatch.setattr(api_module.runtime, "market_close_pause_enabled", False)


def _request(path: str, authorization: str | None = None) -> Request:
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 50000),
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers,
        }
    )


def test_desktop_api_requires_bearer_token(monkeypatch) -> None:
    _safe_runtime(monkeypatch)
    called: list[str] = []

    async def call_next(request: Request) -> JSONResponse:
        called.append(request.url.path)
        return JSONResponse({"status": "CALLED"})

    unauthorized = asyncio.run(
        api_module.desktop_api_authentication(
            _request("/api/desktop/readiness"),
            call_next,
        )
    )
    authorized = asyncio.run(
        api_module.desktop_api_authentication(
            _request(
                "/api/desktop/readiness",
                "Bearer desktop-test-token",
            ),
            call_next,
        )
    )
    legacy_dashboard = asyncio.run(
        api_module.desktop_api_authentication(_request("/"), call_next)
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert legacy_dashboard.status_code == 200
    assert called == ["/api/desktop/readiness", "/"]


def test_desktop_websocket_rejects_missing_token(monkeypatch) -> None:
    _safe_runtime(monkeypatch)

    class FakeWebSocket:
        query_params: dict[str, str] = {}
        close_code: int | None = None

        async def close(self, code: int, reason: str) -> None:
            self.close_code = code
            assert "token" in reason

    websocket = FakeWebSocket()
    asyncio.run(api_module.events_socket(websocket))

    assert websocket.close_code == 4401


def test_desktop_shutdown_requires_explicit_enable(monkeypatch) -> None:
    _safe_runtime(monkeypatch)
    monkeypatch.delenv("NEWXAU_DESKTOP_ALLOW_SHUTDOWN", raising=False)

    disabled = asyncio.run(api_module.request_desktop_shutdown())

    called = False

    def mark_called() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(api_module, "request_shutdown", mark_called)
    monkeypatch.setenv("NEWXAU_DESKTOP_ALLOW_SHUTDOWN", "1")
    enabled = asyncio.run(api_module.request_desktop_shutdown())

    assert disabled.status_code == 403
    assert enabled == {"status": "SHUTTING_DOWN"}
    assert called is True


def test_desktop_runtime_paths_are_independent_of_working_directory(monkeypatch, tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    runtime = tmp_path / "runtime"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("NEWXAU_RESOURCE_ROOT", str(resources))
    monkeypatch.setenv("NEWXAU_RUNTIME_ROOT", str(runtime))
    monkeypatch.chdir(elsewhere)

    config = RuntimeConfig()

    assert Path(config.model_artifacts_dir) == resources / "models"
    assert Path(config.reports_dir) == runtime / "reports"
    assert resolve_resource_path("db/schema.sql") == resources / "db" / "schema.sql"
    assert resolve_runtime_path("logs") == runtime / "logs"


def test_desktop_runtime_reports_execution_safety(monkeypatch, tmp_path: Path) -> None:
    _safe_runtime(monkeypatch)
    monkeypatch.setenv("NEWXAU_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("NEWXAU_RESOURCE_ROOT", str(tmp_path / "resources"))
    monkeypatch.setattr(api_module.runtime, "capital_execution_enabled", False)
    monkeypatch.setattr(api_module.runtime, "capital_execution_auto_execute", False)
    monkeypatch.setattr(api_module.runtime, "capital_execution_demo_only", True)

    response = asyncio.run(api_module.get_desktop_runtime())

    assert response["execution"] == {
        "enabled": False,
        "auto_execute": False,
        "demo_only": True,
    }
