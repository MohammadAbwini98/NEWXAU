from __future__ import annotations

import json
from pathlib import Path

from gold_signal_system.api import app


ROOT = Path(__file__).resolve().parents[1]


def test_pre_electron_rest_contracts_are_still_registered() -> None:
    baseline = json.loads(
        (ROOT / "desktop/verification/baseline/endpoints.json").read_text(encoding="utf-8")
    )
    current = {
        (method, route.path)
        for route in app.routes
        for method in (getattr(route, "methods", None) or set())
    }
    expected = {
        (endpoint["method"], endpoint["path"])
        for endpoint in baseline
        if endpoint["path"]
    }

    assert expected <= current


def test_websocket_route_and_event_names_remain_present() -> None:
    baseline = json.loads(
        (ROOT / "desktop/verification/baseline/websocket-events.json").read_text(
            encoding="utf-8"
        )
    )
    source = (ROOT / "src/gold_signal_system/api.py").read_text(encoding="utf-8")
    websocket_paths = {getattr(route, "path", "") for route in app.routes}

    for websocket in baseline["websockets"]:
        assert websocket["path"] in websocket_paths
    for event in baseline["events"]:
        assert event in source
