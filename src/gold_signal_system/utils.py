from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta


def timeframe_minutes(timeframe: str) -> int:
    return {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "1h": 60,
    }.get(timeframe, 1)


def generate_synthetic_candles(
    instrument: str = "XAUUSD",
    timeframe: str = "1m",
    count: int = 600,
    start_price: float | None = None,
    start_time: datetime | None = None,
) -> list[dict]:
    if start_time is None:
        start_time = datetime.now(tz=UTC) - timedelta(minutes=count)
    if start_price is None:
        inst = instrument.upper()
        if inst.startswith("BTC"):
            start_price = 65000.0
        elif inst.startswith("ETH"):
            start_price = 3000.0
        else:
            start_price = 2350.0

    step_min = timeframe_minutes(timeframe)
    rows: list[dict] = []

    price = start_price
    for i in range(count):
        ts = start_time + timedelta(minutes=i * step_min)
        drift = math.sin(i / 20.0) * 0.3
        shock = math.cos(i / 11.0) * 0.2
        open_price = price
        close_price = max(1.0, price + drift + shock)
        high_price = max(open_price, close_price) + abs(math.sin(i / 7.0)) * 0.25
        low_price = min(open_price, close_price) - abs(math.cos(i / 9.0)) * 0.25
        volume = 1200 + abs(math.sin(i / 5.0)) * 300

        rows.append(
            {
                "instrument": instrument,
                "timeframe": timeframe,
                "candle_time": ts.isoformat(),
                "open": round(open_price, 4),
                "high": round(high_price, 4),
                "low": round(low_price, 4),
                "close": round(close_price, 4),
                "volume": round(volume, 2),
            }
        )
        price = close_price

    return rows
