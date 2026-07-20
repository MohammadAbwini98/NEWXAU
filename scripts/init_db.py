from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.config import RuntimeConfig


SQL_FILES = (
    "schema.sql",
    "001_signal_lifecycle.sql",
    "002_improvement_roadmap.sql",
    "003_production_hardening.sql",
    "004_backtest_persistence.sql",
    "005_persistent_runtime_state.sql",
    "006_capital_execution.sql",
    "007_signal_history_indexes.sql",
    "008_live_price_memory_only.sql",
    "009_news_intelligence.sql",
    "010_execution_control.sql",
)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_project_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(ROOT) / path


def _ensure_local_postgres_running() -> None:
    if not _env_flag("LOCAL_POSTGRES_AUTO_START", False):
        return

    data_dir = _resolve_project_path(os.getenv("LOCAL_POSTGRES_DATA_DIR"))
    bin_dir = _resolve_project_path(os.getenv("LOCAL_POSTGRES_BIN_DIR"))
    port = os.getenv("LOCAL_POSTGRES_PORT", "55432")
    if data_dir is None or bin_dir is None or not data_dir.exists():
        return

    pg_isready = bin_dir / "pg_isready.exe"
    pg_ctl = bin_dir / "pg_ctl.exe"
    if not pg_isready.exists() or not pg_ctl.exists():
        return

    ready = subprocess.run(
        [str(pg_isready), "-h", "127.0.0.1", "-p", port],
        capture_output=True,
        text=True,
        check=False,
    )
    if ready.returncode == 0:
        return

    log_dir = Path(ROOT) / "reports" / "runtime"
    log_dir.mkdir(parents=True, exist_ok=True)
    # NOTE: Do NOT use capture_output / PIPE here. `pg_ctl start` launches the
    # long-lived `postgres` daemon, which on Windows inherits the parent's
    # stdout/stderr handles. If those are pipes, the pipe never reaches EOF
    # (the daemon keeps the write end open for its whole lifetime), so
    # subprocess.run() blocks forever draining it even though startup succeeded.
    # Redirecting pg_ctl's own output to a file avoids the pipe entirely.
    ctl_log = log_dir / "pg_ctl_start.log"
    try:
        with open(ctl_log, "w", encoding="utf-8") as ctl_out:
            start = subprocess.run(
                [
                    str(pg_ctl),
                    "-D",
                    str(data_dir),
                    "-o",
                    f"-p {port} -h 127.0.0.1",
                    "-l",
                    str(log_dir / "postgres.log"),
                    "start",
                ],
                stdout=ctl_out,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=60,
            )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Local PostgreSQL start timed out after 60s.") from exc
    if start.returncode != 0:
        detail = ctl_log.read_text(encoding="utf-8", errors="replace").strip()
        raise RuntimeError(f"Local PostgreSQL failed to start: {detail}")

    for _ in range(20):
        ready = subprocess.run(
            [str(pg_isready), "-h", "127.0.0.1", "-p", port],
            capture_output=True,
            text=True,
            check=False,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Local PostgreSQL did not become ready in time.")


def initialize_database() -> dict[str, object]:
    runtime = RuntimeConfig()
    if not runtime.postgres_dsn:
        return {"status": "SKIPPED", "reason": "POSTGRES_DSN is not configured"}
    _ensure_local_postgres_running()

    try:
        import psycopg
        from psycopg import sql
    except Exception as exc:
        return {"status": "ERROR", "reason": f"psycopg unavailable: {exc}"}

    db_dir = Path(ROOT) / "db"
    applied: list[str] = []
    with psycopg.connect(runtime.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            if runtime.postgres_schema:
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", runtime.postgres_schema):
                    raise ValueError(f"Invalid PostgreSQL schema name: {runtime.postgres_schema}")
                identifier = sql.Identifier(runtime.postgres_schema)
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(identifier))
                cur.execute(sql.SQL("SET search_path TO {}, public").format(identifier))

            for filename in SQL_FILES:
                path = db_dir / filename
                if not path.exists():
                    continue
                cur.execute(path.read_text(encoding="utf-8"))
                applied.append(filename)

    return {
        "status": "OK",
        "schema": runtime.postgres_schema or "default",
        "applied": applied,
    }


def main() -> None:
    result = initialize_database()
    print(f"Database initialization: {result['status']}")
    if result.get("schema"):
        print(f"Schema: {result['schema']}")
    if result.get("applied"):
        print("Applied: " + ", ".join(result["applied"]))  # type: ignore[index]
    if result["status"] == "ERROR":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
