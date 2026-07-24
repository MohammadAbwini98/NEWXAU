r"""Backfill historical OHLCV candles into market_candles via Capital.com.

The live CandleProvider only fetches the *latest* <=1000 candles with no date
range, which is far too little to train models. Capital.com's /prices endpoint
does, however, accept a ``to`` cursor, so we can walk backwards 1000 bars at a
time to accumulate months of history.

Usage (PowerShell):
    .\.venv\Scripts\python.exe scripts\backfill_candles.py --timeframe 5m --max-bars 110000

Environment (read from .env automatically via gold_signal_system.config):
    CAPITALCOM_API_KEY / CAPITAL_API_KEY
    CAPITALCOM_IDENTIFIER / CAPITAL_IDENTIFIER
    CAPITALCOM_PASSWORD / CAPITAL_PASSWORD
    CAPITALCOM_EPIC      (default GOLD)
    POSTGRES_DSN, POSTGRES_SCHEMA
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from gold_signal_system.config import RuntimeConfig  # noqa: E402
from gold_signal_system.contracts import Candle  # noqa: E402
from gold_signal_system.data_engine import normalize_timestamp  # noqa: E402
from gold_signal_system.storage import PostgreSQLStorage  # noqa: E402

_RESOLUTION = {
    "1m": "MINUTE",
    "5m": "MINUTE_5",
    "15m": "MINUTE_15",
    "1h": "HOUR",
    "4h": "HOUR_4",
    "1d": "DAY",
}


class CapitalHistoryClient:
    """Minimal Capital.com client that supports backward pagination via ``to``."""

    def __init__(self, runtime: RuntimeConfig) -> None:
        self.runtime = runtime
        self.base = runtime.capitalcom_api_base.rstrip("/")
        if not self.base.endswith("/api/v1"):
            self.base += "/api/v1"
        self.epic = quote(runtime.capitalcom_epic, safe="")
        self.price_side = (runtime.capitalcom_price_side or "mid").strip().lower()
        self._s = requests.Session()
        self._s.headers.update(
            {
                "X-CAP-API-KEY": runtime.capitalcom_api_key or "",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self._authed = False

    def authenticate(self) -> None:
        if self._authed:
            return
        payload = {
            "identifier": self.runtime.capitalcom_identifier,
            "password": self.runtime.capitalcom_password,
            "encryptedPassword": self.runtime.capitalcom_use_encrypted_password,
        }
        resp = self._s.post(f"{self.base}/session", json=payload, timeout=15)
        resp.raise_for_status()
        if resp.headers.get("CST"):
            self._s.headers["CST"] = resp.headers["CST"]
        if resp.headers.get("X-SECURITY-TOKEN"):
            self._s.headers["X-SECURITY-TOKEN"] = resp.headers["X-SECURITY-TOKEN"]
        self._authed = True

    def _price(self, obj: dict | None) -> float:
        if not obj:
            return 0.0
        if self.price_side in ("bid", "ask") and obj.get(self.price_side) is not None:
            return float(obj[self.price_side])
        bid = float(obj.get("bid") or 0.0)
        ask = float(obj.get("ask") or 0.0)
        if bid and ask:
            return (bid + ask) / 2.0
        return bid or ask

    def fetch_window(self, resolution: str, to_cursor: str | None, batch: int = 1000) -> list[dict]:
        params: dict[str, object] = {"resolution": resolution, "max": batch}
        if to_cursor:
            params["to"] = to_cursor
        resp = self._s.get(f"{self.base}/prices/{self.epic}", params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"prices {resp.status_code}: {resp.text[:200]}")
        rows: list[dict] = []
        for row in resp.json().get("prices", []):
            ts = row.get("snapshotTimeUTC") or row.get("snapshotTime")
            if not ts:
                continue
            rows.append(
                {
                    "candle_time": ts,
                    "open": self._price(row.get("openPrice")),
                    "high": self._price(row.get("highPrice")),
                    "low": self._price(row.get("lowPrice")),
                    "close": self._price(row.get("closePrice")),
                    "volume": float(row.get("lastTradedVolume") or row.get("volume") or 0.0),
                    "_raw_ts": ts,
                }
            )
        rows.sort(key=lambda r: r["candle_time"])
        return rows


def _to_candles(rows: list[dict], instrument: str, timeframe: str) -> list[Candle]:
    out: list[Candle] = []
    for r in rows:
        try:
            c = Candle(
                instrument=instrument,
                timeframe=timeframe,
                candle_time=normalize_timestamp(r["candle_time"]),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("volume") or 0.0),
            )
            if c.open <= 0 or c.close <= 0:
                continue
            out.append(c)
        except Exception:
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill historical candles from Capital.com")
    ap.add_argument("--timeframe", default="5m", choices=sorted(_RESOLUTION))
    ap.add_argument("--max-bars", type=int, default=110_000, help="Stop after accumulating this many bars")
    ap.add_argument("--batch", type=int, default=1000, help="Bars per request (<=1000)")
    ap.add_argument("--sleep", type=float, default=0.30, help="Seconds between requests")
    args = ap.parse_args()

    runtime = RuntimeConfig()
    if not runtime.postgres_dsn:
        raise SystemExit("POSTGRES_DSN is not configured.")
    resolution = _RESOLUTION[args.timeframe]
    instrument = runtime.instrument

    client = CapitalHistoryClient(runtime)
    client.authenticate()
    storage = PostgreSQLStorage(runtime.postgres_dsn, runtime.postgres_schema)

    print(f"Backfilling {instrument} {args.timeframe} ({resolution}); target {args.max_bars} bars", flush=True)

    seen_times: set[datetime] = set()
    to_cursor: str | None = None
    total_saved = 0
    requests_made = 0
    earliest_seen: str | None = None

    while total_saved < args.max_bars:
        try:
            rows = client.fetch_window(resolution, to_cursor, batch=args.batch)
        except Exception as exc:
            print(f"  request failed: {exc}", flush=True)
            break
        requests_made += 1
        if not rows:
            print("  no rows returned; reached end of history.", flush=True)
            break

        candles = _to_candles(rows, instrument, args.timeframe)
        new_candles = [c for c in candles if c.candle_time not in seen_times]
        for c in new_candles:
            seen_times.add(c.candle_time)

        if new_candles:
            storage.save_candles(new_candles)
            total_saved += len(new_candles)

        window_earliest = rows[0]["_raw_ts"]
        window_latest = rows[-1]["_raw_ts"]
        print(
            f"  req {requests_made}: {len(rows)} bars [{window_earliest} .. {window_latest}] "
            f"new={len(new_candles)} total={total_saved}",
            flush=True,
        )

        # Stop if pagination is no longer advancing backward.
        if earliest_seen is not None and window_earliest >= earliest_seen:
            print("  pagination not advancing; stopping.", flush=True)
            break
        earliest_seen = window_earliest
        to_cursor = window_earliest  # next window ends just before current earliest
        time.sleep(args.sleep)

    storage.close()
    print(
        f"DONE: saved/updated {total_saved} {args.timeframe} bars in {requests_made} requests "
        f"(earliest {earliest_seen}).",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("interrupted", flush=True)
        raise SystemExit(130)
