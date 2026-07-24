from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import logging
import re
from typing import Any

from .models import (
    MacroEventModel,
    NewsAiAnalysisModel,
    NewsImpactValidationModel,
    NewsSourceHealthModel,
    NormalizedNewsItem,
    SourceHealthStatus,
    StrategyNewsStateModel,
)

logger = logging.getLogger(__name__)


class NewsIntelligenceRepository:
    """Repository for News Intelligence records with PostgreSQL and in-memory fallback."""

    def __init__(
        self,
        dsn: str | None = None,
        schema: str | None = None,
        connect_timeout_seconds: int = 5,
    ) -> None:
        self._dsn = dsn
        self._schema = schema
        self._in_memory = not bool(dsn)
        self._conn: Any | None = None
        self._news_items: list[dict[str, Any]] = []
        self._macro_events: list[dict[str, Any]] = []
        self._ai_analysis: list[dict[str, Any]] = []
        self._strategy_state: dict[str, dict[str, Any]] = {}
        self._source_health: dict[str, dict[str, Any]] = {}
        self._validations: list[dict[str, Any]] = []

        if not self._in_memory:
            try:
                import psycopg
                from psycopg import sql
                from psycopg.rows import dict_row

                self._psycopg = psycopg
                self._sql = sql
                self._conn = psycopg.connect(
                    self._dsn,
                    autocommit=True,
                    row_factory=dict_row,
                    connect_timeout=max(int(connect_timeout_seconds), 1),
                )
                if self._schema:
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self._schema):
                        raise ValueError(f"Invalid PostgreSQL schema name: {self._schema}")
                    with self._conn.cursor() as cur:
                        cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(self._schema)))
            except Exception as exc:
                logger.error("Failed to connect to postgres for NewsIntelligenceRepository: %s", exc)
                self._in_memory = True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()

    def save_news_item(self, item: NormalizedNewsItem, news_hash: str) -> int | None:
        if self._in_memory:
            existing = next((row for row in self._news_items if row.get("news_hash") == news_hash), None)
            if existing:
                return int(existing["id"])
            record = item.model_dump(mode="json")
            record["id"] = len(self._news_items) + 1
            record["news_hash"] = news_hash
            record["created_at"] = datetime.now(tz=UTC).isoformat()
            self._news_items.append(record)
            return int(record["id"])

        row = self._fetchone(
            """
            INSERT INTO news_items (
                instrument, source, title, published_at, collected_at, url,
                raw_text, raw_payload, news_hash, relevance, event_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (news_hash) DO UPDATE SET
                relevance = EXCLUDED.relevance,
                event_type = EXCLUDED.event_type
            RETURNING id
            """,
            (
                item.instrument,
                item.source,
                item.title,
                item.published_at,
                item.collected_at,
                item.url,
                item.raw_text,
                self._json(item.raw_payload),
                news_hash,
                item.relevance,
                item.event_type,
            ),
        )
        return int(row["id"]) if row else None

    def get_news_items(
        self,
        instrument: str,
        limit: int = 50,
        *,
        event_type: str | None = None,
        relevance: str | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._in_memory:
            rows = [row for row in self._news_items if row.get("instrument") == instrument]
            if event_type:
                rows = [row for row in rows if str(row.get("event_type")).upper() == event_type.upper()]
            if relevance:
                rows = [row for row in rows if str(row.get("relevance")).upper() == relevance.upper()]
            if source:
                rows = [row for row in rows if str(row.get("source")).lower() == source.lower()]
            rows.sort(key=lambda row: row.get("published_at") or row.get("collected_at") or "", reverse=True)
            return rows[: max(limit, 1)]

        clauses = ["instrument = %s"]
        params: list[Any] = [instrument]
        if event_type:
            clauses.append("upper(event_type) = %s")
            params.append(event_type.upper())
        if relevance:
            clauses.append("upper(relevance) = %s")
            params.append(relevance.upper())
        if source:
            clauses.append("lower(source) = %s")
            params.append(source.lower())
        params.append(max(int(limit), 1))
        return self._fetchall(
            f"""
            SELECT * FROM news_items
            WHERE {' AND '.join(clauses)}
            ORDER BY published_at DESC NULLS LAST, collected_at DESC
            LIMIT %s
            """,
            tuple(params),
        )

    def save_macro_event(self, event: MacroEventModel, event_hash: str) -> int | None:
        if self._in_memory:
            existing = next((row for row in self._macro_events if row.get("event_hash") == event_hash), None)
            if existing:
                existing.update(event.model_dump(mode="json"))
                existing["updated_at"] = datetime.now(tz=UTC).isoformat()
                return int(existing["id"])
            record = event.model_dump(mode="json")
            record["id"] = len(self._macro_events) + 1
            record["event_hash"] = event_hash
            record["created_at"] = datetime.now(tz=UTC).isoformat()
            record["updated_at"] = record["created_at"]
            self._macro_events.append(record)
            return int(record["id"])

        row = self._fetchone(
            """
            INSERT INTO macro_events (
                event_type, title, country, currency, scheduled_at, importance,
                forecast_value, previous_value, actual_value, source, url,
                raw_payload, event_hash, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (event_hash) DO UPDATE SET
                title = EXCLUDED.title,
                forecast_value = EXCLUDED.forecast_value,
                previous_value = EXCLUDED.previous_value,
                actual_value = EXCLUDED.actual_value,
                status = EXCLUDED.status,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = now()
            RETURNING id
            """,
            (
                event.event_type,
                event.title,
                event.country,
                event.currency,
                event.scheduled_at,
                event.importance,
                event.forecast_value,
                event.previous_value,
                event.actual_value,
                event.source,
                event.url,
                self._json(event.raw_payload),
                event_hash,
                event.status,
            ),
        )
        return int(row["id"]) if row else None

    def get_macro_events(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        start = start or (datetime.now(tz=UTC) - timedelta(hours=24))
        end = end or (datetime.now(tz=UTC) + timedelta(days=14))
        if self._in_memory:
            rows = []
            for row in self._macro_events:
                scheduled = self._parse_dt(row.get("scheduled_at"))
                if scheduled is None or scheduled < start or scheduled > end:
                    continue
                if event_type and str(row.get("event_type")).upper() != event_type.upper():
                    continue
                rows.append(row)
            rows.sort(key=lambda row: row.get("scheduled_at") or "")
            return rows[: max(limit, 1)]
        clauses = ["scheduled_at >= %s", "scheduled_at <= %s"]
        params: list[Any] = [start, end]
        if event_type:
            clauses.append("upper(event_type) = %s")
            params.append(event_type.upper())
        params.append(max(int(limit), 1))
        return self._fetchall(
            f"""
            SELECT * FROM macro_events
            WHERE {' AND '.join(clauses)}
            ORDER BY scheduled_at ASC
            LIMIT %s
            """,
            tuple(params),
        )

    def get_upcoming_macro_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.get_macro_events(limit=limit)

    def update_macro_event_actual(self, event_id: int, actual_value: str, status: str = "RELEASED") -> dict[str, Any] | None:
        if self._in_memory:
            row = next((item for item in self._macro_events if int(item.get("id") or 0) == int(event_id)), None)
            if row:
                row["actual_value"] = actual_value
                row["status"] = status
                row["updated_at"] = datetime.now(tz=UTC).isoformat()
            return row
        return self._fetchone(
            """
            UPDATE macro_events
            SET actual_value = %s, status = %s, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (actual_value, status, event_id),
        )

    def save_ai_analysis(
        self,
        analysis: NewsAiAnalysisModel,
        news_item_id: int | None = None,
        macro_event_id: int | None = None,
    ) -> int | None:
        if news_item_id is None and macro_event_id is None:
            return None
        payload = analysis.model_dump(mode="json")
        valid_until = analysis.valid_until
        if valid_until is None and analysis.recommended_strategy_action.valid_until_minutes:
            valid_until = datetime.now(tz=UTC) + timedelta(minutes=analysis.recommended_strategy_action.valid_until_minutes)
        if self._in_memory:
            record = {
                **payload,
                "id": len(self._ai_analysis) + 1,
                "news_item_id": news_item_id,
                "macro_event_id": macro_event_id,
                "reasoning_json": list(analysis.reasoning_points),
                "raw_ai_response": analysis.raw_ai_response or payload,
                "valid_until": valid_until.isoformat() if valid_until else None,
                "news_weight": analysis.recommended_strategy_action.news_weight,
                "max_position_multiplier": analysis.recommended_strategy_action.max_position_multiplier,
                "created_at": datetime.now(tz=UTC).isoformat(),
            }
            self._ai_analysis.append(record)
            return int(record["id"])

        row = self._fetchone(
            """
            INSERT INTO news_ai_analysis (
                news_item_id, macro_event_id, instrument, event_type, news_relevance,
                direction, trade_bias, confidence, impact_strength, expected_time_window,
                market_session, volatility_expected, risk_level, action_level,
                should_block_trading, should_reduce_position_size, summary,
                reasoning_json, raw_ai_response, valid_until, news_weight, max_position_multiplier
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
            """,
            (
                news_item_id,
                macro_event_id,
                analysis.instrument,
                analysis.event_type,
                analysis.news_relevance,
                analysis.direction,
                analysis.trade_bias,
                analysis.confidence,
                analysis.impact_strength,
                analysis.expected_time_window,
                analysis.market_session,
                analysis.volatility_expected,
                analysis.risk_level,
                analysis.action_level,
                analysis.should_block_trading,
                analysis.should_reduce_position_size,
                analysis.summary,
                self._json(analysis.reasoning_points),
                self._json(analysis.raw_ai_response or payload),
                valid_until,
                analysis.recommended_strategy_action.news_weight,
                analysis.recommended_strategy_action.max_position_multiplier,
            ),
        )
        return int(row["id"]) if row else None

    def get_ai_analyses(self, instrument: str, limit: int = 50, *, active_only: bool = False) -> list[dict[str, Any]]:
        if self._in_memory:
            rows = [row for row in self._ai_analysis if row.get("instrument") == instrument]
            if active_only:
                now = datetime.now(tz=UTC)
                rows = [row for row in rows if (self._parse_dt(row.get("valid_until")) or now) > now]
            rows.sort(key=lambda row: row.get("created_at") or row.get("id", 0), reverse=True)
            return rows[: max(limit, 1)]
        where = "instrument = %s"
        params: list[Any] = [instrument]
        if active_only:
            where += " AND valid_until > now()"
        params.append(max(int(limit), 1))
        return self._fetchall(
            f"""
            SELECT * FROM news_ai_analysis
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )

    def save_strategy_news_state(self, state: StrategyNewsStateModel) -> int | None:
        if self._in_memory:
            record = state.model_dump(mode="json")
            record["id"] = self._strategy_state.get(state.instrument, {}).get("id") or len(self._strategy_state) + 1
            self._strategy_state[state.instrument] = record
            return int(record["id"])
        row = self._fetchone(
            """
            INSERT INTO strategy_news_state (
                instrument, active_direction, active_trade_bias, active_confidence,
                active_news_weight, block_trading, reduce_position_size, action_level,
                reason, active_event_type, valid_until, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (instrument) DO UPDATE SET
                active_direction = EXCLUDED.active_direction,
                active_trade_bias = EXCLUDED.active_trade_bias,
                active_confidence = EXCLUDED.active_confidence,
                active_news_weight = EXCLUDED.active_news_weight,
                block_trading = EXCLUDED.block_trading,
                reduce_position_size = EXCLUDED.reduce_position_size,
                action_level = EXCLUDED.action_level,
                reason = EXCLUDED.reason,
                active_event_type = EXCLUDED.active_event_type,
                valid_until = EXCLUDED.valid_until,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            (
                state.instrument,
                state.active_direction,
                state.active_trade_bias,
                state.active_confidence,
                state.active_news_weight,
                state.block_trading,
                state.reduce_position_size,
                state.action_level,
                state.reason,
                state.active_event_type,
                state.valid_until,
            ),
        )
        return int(row["id"]) if row else None

    def get_active_strategy_news_state(self, instrument: str) -> dict[str, Any] | None:
        if self._in_memory:
            row = self._strategy_state.get(instrument)
            return self._clear_if_expired(row) if row else None
        row = self._fetchone("SELECT * FROM strategy_news_state WHERE instrument = %s", (instrument,))
        return self._clear_if_expired(row) if row else None

    def save_validation(self, validation: NewsImpactValidationModel) -> int | None:
        if self._in_memory:
            record = validation.model_dump(mode="json")
            record["id"] = len(self._validations) + 1
            self._validations.append(record)
            return int(record["id"])
        row = self._fetchone(
            """
            INSERT INTO news_impact_validation (
                analysis_id, instrument, evaluated_at, horizon_minutes,
                predicted_direction, actual_direction, price_at_analysis,
                price_at_horizon, return_pct, was_correct, notes
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                validation.analysis_id,
                validation.instrument,
                validation.evaluated_at,
                validation.horizon_minutes,
                validation.predicted_direction,
                validation.actual_direction,
                validation.price_at_analysis,
                validation.price_at_horizon,
                validation.return_pct,
                validation.was_correct,
                validation.notes,
            ),
        )
        return int(row["id"]) if row else None

    def validation_summary(self, instrument: str) -> dict[str, Any]:
        if self._in_memory:
            rows = [row for row in self._validations if row.get("instrument") == instrument]
            return self._summarize_validation_rows(rows)
        rows = self._fetchall(
            """
            SELECT v.*, a.event_type, a.confidence
            FROM news_impact_validation v
            JOIN news_ai_analysis a ON a.id = v.analysis_id
            WHERE v.instrument = %s
            ORDER BY v.evaluated_at DESC
            LIMIT 1000
            """,
            (instrument,),
        )
        return self._summarize_validation_rows(rows)

    def record_source_success(self, source: str) -> None:
        self._save_source_health(NewsSourceHealthModel(source=source, status=SourceHealthStatus.OK.value, last_success_at=datetime.now(tz=UTC)))

    def record_source_failure(self, source: str, error: str) -> None:
        previous = self.get_source_health().get(source, {})
        self._save_source_health(
            NewsSourceHealthModel(
                source=source,
                status=SourceHealthStatus.DEGRADED.value if int(previous.get("consecutive_failures") or 0) < 2 else SourceHealthStatus.FAILED.value,
                last_success_at=self._parse_dt(previous.get("last_success_at")),
                last_error_at=datetime.now(tz=UTC),
                last_error=error[:500],
                consecutive_failures=int(previous.get("consecutive_failures") or 0) + 1,
            )
        )

    def get_source_health(self) -> dict[str, dict[str, Any]]:
        if self._in_memory:
            return dict(self._source_health)
        try:
            rows = self._fetchall("SELECT * FROM news_source_health ORDER BY source", ())
            return {str(row["source"]): row for row in rows}
        except Exception:
            return {}

    def dashboard_summary(self, instrument: str) -> dict[str, Any]:
        return {
            "state": self.get_active_strategy_news_state(instrument) or {},
            "items": self.get_news_items(instrument, limit=20),
            "analysis": self.get_ai_analyses(instrument, limit=20),
            "macro_events": self.get_upcoming_macro_events(limit=20),
            "source_health": self.get_source_health(),
            "validation": self.validation_summary(instrument),
        }

    def _save_source_health(self, health: NewsSourceHealthModel) -> None:
        if self._in_memory:
            payload = health.model_dump(mode="json")
            if health.status == SourceHealthStatus.OK.value:
                payload["consecutive_failures"] = 0
            self._source_health[health.source] = payload
            return
        try:
            self._fetchone(
                """
                INSERT INTO news_source_health (
                    source, status, last_success_at, last_error_at,
                    last_error, consecutive_failures, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (source) DO UPDATE SET
                    status = EXCLUDED.status,
                    last_success_at = COALESCE(EXCLUDED.last_success_at, news_source_health.last_success_at),
                    last_error_at = EXCLUDED.last_error_at,
                    last_error = EXCLUDED.last_error,
                    consecutive_failures = CASE WHEN EXCLUDED.status = 'OK' THEN 0 ELSE EXCLUDED.consecutive_failures END,
                    updated_at = now()
                RETURNING source
                """,
                (
                    health.source,
                    health.status,
                    health.last_success_at,
                    health.last_error_at,
                    health.last_error,
                    health.consecutive_failures,
                ),
            )
        except Exception as exc:
            logger.warning("Failed to persist news source health: %s", exc)

    def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        if self._in_memory or self._conn is None:
            return
        with self._conn.cursor() as cur:
            cur.execute(query, params)

    def _fetchone(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        if self._in_memory or self._conn is None:
            return None
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return self._coerce_row(row) if row else None

    def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        if self._in_memory or self._conn is None:
            return []
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            return [self._coerce_row(row) for row in cur.fetchall()]

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value or {}, default=str)

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except Exception:
            return None

    @classmethod
    def _clear_if_expired(cls, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        valid_until = cls._parse_dt(row.get("valid_until"))
        if valid_until and valid_until < datetime.now(tz=UTC):
            return {
                **row,
                "active_direction": "NEUTRAL",
                "active_trade_bias": "HOLD",
                "active_confidence": 0.0,
                "active_news_weight": 0.0,
                "block_trading": False,
                "reduce_position_size": False,
                "action_level": "INFO_ONLY",
                "reason": "News state expired.",
            }
        return row

    @staticmethod
    def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        for key, value in list(data.items()):
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data

    @staticmethod
    def _summarize_validation_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(rows)
        correct = sum(1 for row in rows if row.get("was_correct"))
        by_event: dict[str, dict[str, int]] = {}
        by_bucket: dict[str, dict[str, int]] = {}
        for row in rows:
            event = str(row.get("event_type") or "UNKNOWN")
            bucket = NewsIntelligenceRepository._confidence_bucket(float(row.get("confidence") or 0.0))
            by_event.setdefault(event, {"total": 0, "correct": 0})
            by_bucket.setdefault(bucket, {"total": 0, "correct": 0})
            by_event[event]["total"] += 1
            by_bucket[bucket]["total"] += 1
            if row.get("was_correct"):
                by_event[event]["correct"] += 1
                by_bucket[bucket]["correct"] += 1
        return {
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total else 0.0,
            "by_event_type": {
                key: {**value, "accuracy": round(value["correct"] / value["total"], 4) if value["total"] else 0.0}
                for key, value in by_event.items()
            },
            "by_confidence_bucket": {
                key: {**value, "accuracy": round(value["correct"] / value["total"], 4) if value["total"] else 0.0}
                for key, value in by_bucket.items()
            },
        }

    @staticmethod
    def _confidence_bucket(confidence: float) -> str:
        if confidence < 0.50:
            return "0.00-0.49"
        if confidence < 0.60:
            return "0.50-0.59"
        if confidence < 0.70:
            return "0.60-0.69"
        if confidence < 0.80:
            return "0.70-0.79"
        if confidence < 0.90:
            return "0.80-0.89"
        return "0.90-1.00"
