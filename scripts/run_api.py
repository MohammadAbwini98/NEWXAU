from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import threading
import time
import webbrowser

import uvicorn

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from scripts.init_db import initialize_database

HOST = "127.0.0.1"
PORT = 8000


def _pids_from_windows_netstat(output: str, port: int) -> set[int]:
    pids: set[int] = set()
    pattern = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE)
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            pids.add(int(match.group(1)))
    return pids


def _running_pids_on_port(port: int) -> set[int]:
    if platform.system().lower() == "windows":
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=False,
        )
        return _pids_from_windows_netstat(result.stdout, port)

    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {int(pid) for pid in result.stdout.splitlines() if pid.strip().isdigit()}


def _kill_pid(pid: int) -> None:
    if pid == os.getpid():
        return
    if platform.system().lower() == "windows":
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, text=True, check=False)
    else:
        subprocess.run(["kill", "-TERM", str(pid)], capture_output=True, text=True, check=False)


def kill_existing_dashboard_processes(port: int = PORT) -> None:
    pids = _running_pids_on_port(port)
    for pid in sorted(pids):
        print(f"Stopping existing dashboard process on port {port}: PID {pid}", flush=True)
        _kill_pid(pid)

    if pids:
        time.sleep(1)


def open_dashboard_when_ready(host: str = HOST, port: int = PORT) -> None:
    url = f"http://{host}:{port}/"

    def _open() -> None:
        time.sleep(2)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    print(f"Starting XAUUSD Signal Desk from {ROOT}", flush=True)
    print(f"Checking port {PORT}...", flush=True)
    kill_existing_dashboard_processes(PORT)
    print("Initializing database...", flush=True)
    db_result = initialize_database()
    print(f"Database initialization: {db_result['status']}", flush=True)
    if db_result.get("schema"):
        print(f"Database schema: {db_result['schema']}", flush=True)
    print(f"Dashboard URL: http://{HOST}:{PORT}/", flush=True)
    print("Leave this terminal open while the dashboard is running. Press Ctrl+C to stop.", flush=True)
    open_dashboard_when_ready(HOST, PORT)
    uvicorn.run("gold_signal_system.api:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
