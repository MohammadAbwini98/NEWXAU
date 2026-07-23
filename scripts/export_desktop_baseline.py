from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
API_PATH = SRC / "gold_signal_system" / "api.py"
BASELINE_DIR = ROOT / "desktop" / "verification" / "baseline"
OPENAPI_DIR = ROOT / "desktop" / "openapi"

ROUTE_DECORATORS = {"get", "post", "put", "patch", "delete", "options", "head"}
HASH_PATTERNS = (
    "db/**/*.sql",
    "src/gold_signal_system/api.py",
    "src/gold_signal_system/contracts.py",
    "src/gold_signal_system/capital_execution.py",
    "src/gold_signal_system/execution_control.py",
    "src/gold_signal_system/market_sessions.py",
    "src/gold_signal_system/models.py",
    "src/dashboard_static/**/*",
)
SECRET_MARKERS = ("SECRET", "PASSWORD", "TOKEN", "API_KEY", "IDENTIFIER")


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _endpoint_inventory(tree: ast.AST) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            name = _call_name(decorator.func)
            method = name.rsplit(".", 1)[-1]
            if not name.startswith("app.") or method not in ROUTE_DECORATORS:
                continue
            path = _literal_string(decorator.args[0]) if decorator.args else None
            endpoints.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "handler": node.name,
                    "line": node.lineno,
                }
            )
    return sorted(endpoints, key=lambda item: (str(item["path"]), item["method"]))


def _websocket_inventory(tree: ast.AST, source: str) -> dict[str, Any]:
    sockets: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and _call_name(decorator.func) == "app.websocket"
                and decorator.args
            ):
                sockets.append(
                    {
                        "path": _literal_string(decorator.args[0]),
                        "handler": node.name,
                        "line": node.lineno,
                    }
                )

    literal_events = set(re.findall(r'"event"\s*:\s*"([^"]+)"', source))
    conditional_events = set(
        re.findall(r'"event"\s*:\s*"([^"]+)"\s+if\s+[^:\n]+\s+else\s+"([^"]+)"', source)
    )
    for first, second in conditional_events:
        literal_events.add(first)
        literal_events.add(second)
    return {
        "websockets": sockets,
        "events": sorted(literal_events),
        "envelope": {
            "required_fields": ["event", "occurred_at", "data"],
            "heartbeat_event": "heartbeat",
        },
    }


def _environment_inventory() -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted([*SRC.rglob("*.py"), *(ROOT / "scripts").rglob("*.py")]):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node.func) not in {
                "os.getenv",
                "os.environ.get",
            }:
                continue
            if not node.args:
                continue
            name = _literal_string(node.args[0])
            if not name:
                continue
            default = _literal_string(node.args[1]) if len(node.args) > 1 else None
            secret = any(marker in name.upper() for marker in SECRET_MARKERS)
            item = found.setdefault(
                name,
                {
                    "name": name,
                    "default": None if secret else default,
                    "secret": secret,
                    "references": [],
                },
            )
            reference = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
            if reference not in item["references"]:
                item["references"].append(reference)
    return sorted(found.values(), key=lambda item: item["name"])


def _hash_inventory() -> list[dict[str, str]]:
    paths: set[Path] = set()
    for pattern in HASH_PATTERNS:
        paths.update(path for path in ROOT.glob(pattern) if path.is_file())
    inventory: list[dict[str, str]] = []
    for path in sorted(paths):
        inventory.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return inventory


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _export_openapi() -> None:
    safe_env = {
        "ENABLE_BACKGROUND_CYCLE_RUNNER": "0",
        "ENABLE_LIVE_PRICE_STREAM": "0",
        "CAPITAL_EXECUTION_ENABLED": "0",
        "CAPITAL_EXECUTION_DEMO_ONLY": "1",
    }
    for key, value in safe_env.items():
        os.environ.setdefault(key, value)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from gold_signal_system.api import app

    _write_json(OPENAPI_DIR / "openapi.json", app.openapi())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze NEWXAU desktop migration contracts.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace the existing canonical baseline. Use only for an explicitly approved re-baseline.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    protected_outputs = (
        BASELINE_DIR / "endpoints.json",
        BASELINE_DIR / "websocket-events.json",
        BASELINE_DIR / "environment.json",
        BASELINE_DIR / "protected-file-hashes.json",
        OPENAPI_DIR / "openapi.json",
    )
    if not args.force and any(path.exists() for path in protected_outputs):
        raise SystemExit(
            "The canonical pre-Electron baseline already exists. "
            "Pass --force only for an explicitly approved re-baseline."
        )
    source = API_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(API_PATH))
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(BASELINE_DIR / "endpoints.json", _endpoint_inventory(tree))
    _write_json(BASELINE_DIR / "websocket-events.json", _websocket_inventory(tree, source))
    _write_json(BASELINE_DIR / "environment.json", _environment_inventory())
    _write_json(BASELINE_DIR / "protected-file-hashes.json", _hash_inventory())
    _export_openapi()
    print(f"Desktop migration baseline exported to {BASELINE_DIR}")


if __name__ == "__main__":
    main()
