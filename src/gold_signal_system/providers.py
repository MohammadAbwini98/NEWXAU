from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import requests

from .config import RuntimeConfig
from .utils import generate_synthetic_candles


class CandleProvider(Protocol):
    def fetch_latest_candles(self, instrument: str, timeframe: str, limit: int) -> list[dict]:
        ...


class SyntheticCandleProvider:
    def fetch_latest_candles(self, instrument: str, timeframe: str, limit: int) -> list[dict]:
        return generate_synthetic_candles(instrument=instrument, timeframe=timeframe, count=limit)


@dataclass(slots=True)
class CsvCandleProvider:
    csv_path: str

    def fetch_latest_candles(self, instrument: str, timeframe: str, limit: int) -> list[dict]:
        path = Path(self.csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV candle file not found: {path}")

        rows: list[dict] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("instrument", instrument) != instrument:
                    continue
                if row.get("timeframe", timeframe) != timeframe:
                    continue
                rows.append(
                    {
                        "candle_time": row["candle_time"],
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row.get("volume", 0.0) or 0.0),
                    }
                )

        rows.sort(key=lambda r: r["candle_time"])
        return rows[-limit:]


@dataclass(slots=True)
class CapitalComCandleProvider:
    api_base: str
    api_key: str
    identifier: str
    password: str
    epic: str
    price_side: str = "mid"
    use_encrypted_password: bool = False
    _session: requests.Session = field(init=False, repr=False)
    _authenticated: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-CAP-API-KEY": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self._authenticated = False

    def _build_url(self, path: str) -> str:
        base = self._normalized_api_base()
        return f"{base}{path}"

    def _normalized_api_base(self) -> str:
        base = self.api_base.rstrip("/")
        if base.endswith("/api/v1"):
            return base
        return f"{base}/api/v1"

    def _authenticate(self) -> None:
        if self._authenticated:
            return

        payload = {
            "identifier": self.identifier,
            "password": self.password,
            "encryptedPassword": self.use_encrypted_password,
        }
        resp = self._session.post(self._build_url("/session"), json=payload, timeout=15)
        resp.raise_for_status()

        cst = resp.headers.get("CST")
        x_security_token = resp.headers.get("X-SECURITY-TOKEN")
        if not cst or not x_security_token:
            raise RuntimeError("Capital.com auth response did not include CST/X-SECURITY-TOKEN.")
        self._session.headers["CST"] = cst
        self._session.headers["X-SECURITY-TOKEN"] = x_security_token

        self._authenticated = True

    def _invalidate_session(self) -> None:
        self._authenticated = False
        self._session.headers.pop("CST", None)
        self._session.headers.pop("X-SECURITY-TOKEN", None)

    def _get_authenticated(self, path: str, **kwargs: Any) -> requests.Response:
        self._authenticate()
        response = self._session.get(self._build_url(path), **kwargs)
        if response.status_code != 401:
            response.raise_for_status()
            return response

        self._invalidate_session()
        self._authenticate()
        response = self._session.get(self._build_url(path), **kwargs)
        response.raise_for_status()
        return response

    def _timeframe_to_resolution(self, timeframe: str) -> str:
        key = (timeframe or "").strip()
        upper = key.upper()
        if upper in {"MINUTE", "MINUTE_5", "MINUTE_15", "MINUTE_30", "HOUR", "HOUR_4", "DAY", "WEEK"}:
            return upper
        return {
            "1m": "MINUTE",
            "5m": "MINUTE_5",
            "15m": "MINUTE_15",
            "1h": "HOUR",
            "4h": "HOUR_4",
        }.get(key, "MINUTE")

    def _price(self, bid_ask_obj: dict | None) -> float:
        if not bid_ask_obj:
            return 0.0
        side = (self.price_side or "mid").strip().lower()
        if side in ("bid", "ask"):
            value = bid_ask_obj.get(side)
            if value is not None:
                return float(value)
        bid = float(bid_ask_obj.get("bid") or 0.0)
        ask = float(bid_ask_obj.get("ask") or 0.0)
        if bid and ask:
            return (bid + ask) / 2.0
        return bid or ask

    def fetch_latest_candles(self, instrument: str, timeframe: str, limit: int) -> list[dict]:
        resolution = self._timeframe_to_resolution(timeframe)
        params = {
            "resolution": resolution,
            "max": max(10, min(limit, 1000)),
        }

        resp = self._get_authenticated(
            f"/prices/{quote(self.epic, safe='')}",
            params=params,
            timeout=20,
        )
        payload = resp.json()
        prices = payload.get("prices") or []

        rows: list[dict] = []
        for row in prices:
            ts = (
                row.get("snapshotTimeUTC")
                or row.get("snapshotTime")
                or datetime.now(tz=UTC).isoformat()
            )

            o = self._price(row.get("openPrice"))
            h = self._price(row.get("highPrice"))
            l = self._price(row.get("lowPrice"))
            c = self._price(row.get("closePrice"))
            volume = float(row.get("lastTradedVolume") or row.get("volume") or 0.0)

            rows.append(
                {
                    "candle_time": ts,
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": c,
                    "volume": volume,
                }
            )

        rows.sort(key=lambda r: r["candle_time"])
        return rows[-limit:]


def build_candle_provider(runtime: RuntimeConfig) -> CandleProvider:
    provider_name = (runtime.data_provider or "capitalcom").strip().lower()

    if provider_name == "csv":
        if not runtime.candle_csv_path:
            raise ValueError("DATA_PROVIDER=csv requires CANDLE_CSV_PATH")
        return CsvCandleProvider(csv_path=runtime.candle_csv_path)

    if provider_name in ("capitalcom", "capital", "capital.com"):
        missing = [
            key
            for key, value in {
                "CAPITAL_API_KEY/CAPITALCOM_API_KEY": runtime.capitalcom_api_key,
                "CAPITAL_IDENTIFIER/CAPITALCOM_IDENTIFIER": runtime.capitalcom_identifier,
                "CAPITAL_PASSWORD/CAPITALCOM_PASSWORD": runtime.capitalcom_password,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"DATA_PROVIDER=capitalcom missing env vars: {', '.join(missing)}")

        return CapitalComCandleProvider(
            api_base=runtime.capitalcom_api_base,
            api_key=runtime.capitalcom_api_key or "",
            identifier=runtime.capitalcom_identifier or "",
            password=runtime.capitalcom_password or "",
            epic=runtime.capitalcom_epic,
            price_side=runtime.capitalcom_price_side,
            use_encrypted_password=runtime.capitalcom_use_encrypted_password,
        )

    if provider_name in ("synthetic", "mock"):
        return SyntheticCandleProvider()

    raise ValueError(f"Unsupported DATA_PROVIDER: {runtime.data_provider}")
