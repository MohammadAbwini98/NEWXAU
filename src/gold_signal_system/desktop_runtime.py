from __future__ import annotations

import asyncio
import os
from pathlib import Path


_shutdown_requested = asyncio.Event()


def resource_root() -> Path:
    configured = os.getenv("NEWXAU_RESOURCE_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def runtime_root() -> Path:
    configured = os.getenv("NEWXAU_RUNTIME_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return resource_root() / "runtime"


def resolve_resource_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (resource_root() / path).resolve()


def resolve_runtime_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (runtime_root() / path).resolve()


def request_shutdown() -> None:
    _shutdown_requested.set()


async def wait_for_shutdown_request() -> None:
    await _shutdown_requested.wait()


def reset_shutdown_request() -> None:
    _shutdown_requested.clear()
