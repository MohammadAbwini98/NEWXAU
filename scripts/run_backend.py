from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gold_signal_system.desktop_runtime import reset_shutdown_request, wait_for_shutdown_request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the NEWXAU backend without opening a browser.")
    parser.add_argument("--host", default=os.getenv("NEWXAU_BACKEND_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("NEWXAU_BACKEND_PORT", "0")))
    parser.add_argument("--log-level", default=os.getenv("NEWXAU_BACKEND_LOG_LEVEL", "warning"))
    return parser.parse_args()


async def serve(host: str, port: int, log_level: str) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("The desktop backend may only bind to loopback.")
    reset_shutdown_request()
    config = uvicorn.Config(
        "gold_signal_system.api:app",
        host="127.0.0.1",
        port=port,
        reload=False,
        log_level=log_level,
        access_log=False,
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    while not server.started and not server_task.done():
        await asyncio.sleep(0.025)
    if server_task.done():
        await server_task
        return

    bound_port = port
    if port == 0 and server.servers:
        sockets = server.servers[0].sockets or []
        if sockets:
            bound_port = int(sockets[0].getsockname()[1])
    print(
        json.dumps(
            {
                "event": "ready",
                "host": "127.0.0.1",
                "port": bound_port,
                "pid": os.getpid(),
            }
        ),
        flush=True,
    )

    shutdown_task = asyncio.create_task(wait_for_shutdown_request())
    completed, _ = await asyncio.wait(
        {server_task, shutdown_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if shutdown_task in completed:
        server.should_exit = True
    await server_task
    shutdown_task.cancel()


def main() -> None:
    args = parse_args()
    asyncio.run(serve(args.host, args.port, args.log_level))


if __name__ == "__main__":
    main()
