from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Iterable, Optional

from dateutil import parser

from .contracts import Candle, DataQualityReport


_TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}


def timeframe_to_delta(timeframe: str) -> timedelta:
    if timeframe not in _TIMEFRAME_DELTAS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return _TIMEFRAME_DELTAS[timeframe]


def normalize_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, str):
        dt = parser.isoparse(value)
    else:
        dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _floor_time(timestamp: datetime, timeframe: str) -> datetime:
    timestamp = normalize_timestamp(timestamp)
    if timeframe == "1m":
        return timestamp.replace(second=0, microsecond=0)
    if timeframe == "5m":
        minute = (timestamp.minute // 5) * 5
        return timestamp.replace(minute=minute, second=0, microsecond=0)
    if timeframe == "15m":
        minute = (timestamp.minute // 15) * 15
        return timestamp.replace(minute=minute, second=0, microsecond=0)
    if timeframe == "30m":
        minute = (timestamp.minute // 30) * 30
        return timestamp.replace(minute=minute, second=0, microsecond=0)
    if timeframe == "1h":
        return timestamp.replace(minute=0, second=0, microsecond=0)
    if timeframe == "4h":
        hour = (timestamp.hour // 4) * 4
        return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported timeframe: {timeframe}")


class DataEngine:
    """Phase 1: collect, clean, validate, and aggregate candle data."""

    @staticmethod
    def timeframe_seconds(timeframe: str) -> float:
        return timeframe_to_delta(timeframe).total_seconds()

    def clean_candles(
        self,
        raw_candles: Iterable[dict],
        instrument: str,
        timeframe: str,
        reference_time: datetime | None = None,
        provider_status: str = "UNKNOWN",
        max_missing_ratio: float = 0.02,
        max_outlier_ratio: float = 0.01,
        max_freshness_seconds: float | None = None,
        minimum_quality_score: float = 85.0,
    ) -> tuple[list[Candle], DataQualityReport]:
        raw_rows = list(raw_candles)
        parsed: list[Candle] = []
        invalid_rows = 0
        issues: list[str] = []

        for idx, row in enumerate(raw_rows):
            try:
                candle = Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    candle_time=normalize_timestamp(row["candle_time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]) if row.get("volume") is not None else None,
                )
                parsed.append(candle)
            except Exception as exc:
                invalid_rows += 1
                issues.append(f"Row {idx} invalid: {exc}")

        out_of_order_count = sum(
            1
            for previous, current in zip(parsed, parsed[1:])
            if current.candle_time < previous.candle_time
        )
        if out_of_order_count:
            issues.append(f"Out-of-order candles detected: {out_of_order_count}")

        parsed.sort(key=lambda c: c.candle_time)

        deduped: list[Candle] = []
        seen: set[tuple[str, str, datetime]] = set()
        duplicate_rows = 0
        for candle in parsed:
            key = (candle.instrument, candle.timeframe, candle.candle_time)
            if key in seen:
                duplicate_rows += 1
                continue
            seen.add(key)
            deduped.append(candle)

        missing_timestamps = self.detect_missing_candles(deduped, timeframe)
        if missing_timestamps:
            issues.append(f"Missing candles detected: {len(missing_timestamps)}")

        outlier_count = self.detect_price_outliers(deduped)
        if outlier_count:
            issues.append(f"Price outliers detected: {outlier_count}")

        freshness_seconds: float | None = None
        if reference_time is not None and deduped:
            normalized_reference = normalize_timestamp(reference_time)
            freshness_seconds = max(0.0, (normalized_reference - deduped[-1].candle_time).total_seconds())

        expected_rows = len(deduped) + len(missing_timestamps)
        missing_ratio = len(missing_timestamps) / max(expected_rows, 1)
        outlier_ratio = outlier_count / max(len(deduped), 1)
        invalid_ratio = invalid_rows / max(len(raw_rows), 1)
        duplicate_ratio = duplicate_rows / max(len(raw_rows), 1)

        blocking_reasons: list[str] = []
        normalized_provider_status = str(provider_status or "UNKNOWN").strip().upper()
        if not deduped:
            blocking_reasons.append("No valid candles are available.")
        if normalized_provider_status in {"FAILED", "UNAVAILABLE", "ERROR"}:
            blocking_reasons.append(f"Provider status is {normalized_provider_status}.")
        if missing_ratio > max_missing_ratio:
            blocking_reasons.append(
                f"Missing-candle ratio {missing_ratio:.2%} exceeds {max_missing_ratio:.2%}."
            )
        if outlier_ratio > max_outlier_ratio:
            blocking_reasons.append(
                f"Price-outlier ratio {outlier_ratio:.2%} exceeds {max_outlier_ratio:.2%}."
            )
        if (
            max_freshness_seconds is not None
            and freshness_seconds is not None
            and freshness_seconds > max_freshness_seconds
        ):
            blocking_reasons.append(
                f"Latest candle is stale ({freshness_seconds:.1f}s > {max_freshness_seconds:.1f}s)."
            )

        quality_score = 100.0
        quality_score -= min(45.0, missing_ratio * 500.0)
        quality_score -= min(25.0, invalid_ratio * 250.0)
        quality_score -= min(15.0, duplicate_ratio * 150.0)
        quality_score -= min(25.0, outlier_ratio * 250.0)
        quality_score -= min(10.0, out_of_order_count / max(len(parsed), 1) * 100.0)
        if (
            max_freshness_seconds is not None
            and freshness_seconds is not None
            and freshness_seconds > max_freshness_seconds
        ):
            quality_score -= 25.0
        quality_score = round(max(0.0, quality_score), 2)
        if quality_score < minimum_quality_score:
            blocking_reasons.append(
                f"Data quality score {quality_score:.2f} is below {minimum_quality_score:.2f}."
            )

        report = DataQualityReport(
            total_rows=len(raw_rows),
            cleaned_rows=len(deduped),
            duplicate_rows=duplicate_rows,
            invalid_rows=invalid_rows,
            missing_candles_count=len(missing_timestamps),
            missing_timestamps=missing_timestamps,
            issues=issues,
            quality_score=quality_score,
            freshness_seconds=freshness_seconds,
            missing_candles=len(missing_timestamps),
            duplicate_candles=duplicate_rows,
            outlier_count=outlier_count,
            out_of_order_count=out_of_order_count,
            provider_status=normalized_provider_status,
            blocking_reasons=blocking_reasons,
        )

        return deduped, report

    def detect_missing_candles(self, candles: list[Candle], timeframe: str) -> list[datetime]:
        if len(candles) < 2:
            return []

        delta = timeframe_to_delta(timeframe)
        expected = candles[0].candle_time
        last_time = candles[-1].candle_time
        observed = {c.candle_time for c in candles}

        missing: list[datetime] = []
        while expected <= last_time:
            if expected not in observed:
                missing.append(expected)
            expected += delta
        return missing

    def detect_price_outliers(self, candles: list[Candle]) -> int:
        """Return a robust count of extreme close-to-close moves.

        The median absolute deviation adapts to the current series and the 1% floor
        avoids labelling ordinary low-volatility price changes as corrupt data.
        """
        if len(candles) < 5:
            return 0
        returns = [
            abs((current.close - previous.close) / previous.close)
            for previous, current in zip(candles, candles[1:])
            if previous.close != 0
        ]
        if not returns:
            return 0
        center = median(returns)
        mad = median(abs(value - center) for value in returns)
        threshold = max(0.01, center + 12.0 * max(mad, 1e-9))
        return sum(1 for value in returns if value > threshold)

    def aggregate_from_1m(
        self,
        candles_1m: list[Candle],
        target_timeframe: str,
        require_complete: bool = False,
    ) -> list[Candle]:
        if target_timeframe not in ("5m", "15m", "30m", "1h", "4h"):
            raise ValueError("target_timeframe must be one of 5m, 15m, 30m, 1h, 4h")

        if not candles_1m:
            return []

        grouped: dict[datetime, list[Candle]] = defaultdict(list)
        for candle in candles_1m:
            if candle.timeframe != "1m":
                raise ValueError("aggregate_from_1m accepts only 1m candles")
            bucket = _floor_time(candle.candle_time, target_timeframe)
            grouped[bucket].append(candle)

        aggregated: list[Candle] = []
        expected_count = int(timeframe_to_delta(target_timeframe) / timeframe_to_delta("1m"))
        for bucket in sorted(grouped.keys()):
            chunk = sorted(grouped[bucket], key=lambda c: c.candle_time)
            if require_complete:
                expected_times = {
                    bucket + (timeframe_to_delta("1m") * offset)
                    for offset in range(expected_count)
                }
                if len(chunk) != expected_count or {c.candle_time for c in chunk} != expected_times:
                    continue
            aggregated.append(
                Candle(
                    instrument=chunk[0].instrument,
                    timeframe=target_timeframe,
                    candle_time=bucket,
                    open=chunk[0].open,
                    high=max(c.high for c in chunk),
                    low=min(c.low for c in chunk),
                    close=chunk[-1].close,
                    volume=sum(c.volume or 0.0 for c in chunk),
                )
            )
        return aggregated


class InMemoryCandleStore:
    """Simple repository that mimics a clean candle table for local runs."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, datetime], Candle] = {}

    def upsert_many(self, candles: list[Candle]) -> int:
        upserted = 0
        for candle in candles:
            key = (candle.instrument, candle.timeframe, candle.candle_time)
            self._rows[key] = candle
            upserted += 1
        return upserted

    def get(
        self,
        instrument: str,
        timeframe: str,
        limit: Optional[int] = None,
    ) -> list[Candle]:
        rows = [
            candle
            for (inst, tf, _), candle in self._rows.items()
            if inst == instrument and tf == timeframe
        ]
        rows.sort(key=lambda c: c.candle_time)
        if limit is None:
            return rows
        return rows[-limit:]
