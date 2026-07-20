from __future__ import annotations

import logging
from typing import Any

from .ai_analyzer import AiNewsAnalyzer
from .collectors import (
    CapitalComRelatedNewsCollector,
    NewsCollector,
    RssNewsCollector,
    generate_news_hash,
    normalize_news_payload,
)
from .macro_events import MacroEventIngestor, current_risk_window
from .models import MacroEventModel, NormalizedNewsItem
from .repository import NewsIntelligenceRepository
from .strategy_integration import NewsStateAggregator
from .validation import NewsImpactValidator

logger = logging.getLogger(__name__)


class NewsIntelligenceService:
    def __init__(
        self,
        *,
        repository: NewsIntelligenceRepository,
        runtime: Any,
        collectors: list[NewsCollector] | None = None,
        analyzer: AiNewsAnalyzer | None = None,
        aggregator: NewsStateAggregator | None = None,
    ) -> None:
        self.repository = repository
        self.runtime = runtime
        self.analyzer = analyzer or AiNewsAnalyzer(runtime)
        self.aggregator = aggregator or NewsStateAggregator(repository, runtime)
        self.macro_ingestor = MacroEventIngestor(repository)
        self.validator = NewsImpactValidator(repository)
        self.collectors = collectors if collectors is not None else self._build_collectors()

    def _build_collectors(self) -> list[NewsCollector]:
        urls = [
            item.strip()
            for item in str(getattr(self.runtime, "news_rss_urls", "") or "").split(",")
            if item.strip()
        ]
        collectors: list[NewsCollector] = [RssNewsCollector(urls)]
        if getattr(self.runtime, "news_capital_related_enabled", False):
            collectors.append(
                CapitalComRelatedNewsCollector(
                    session_state_path=getattr(self.runtime, "news_capital_session_state_path", None),
                    exported_news_path=getattr(self.runtime, "news_capital_exported_news_path", None),
                    platform_url=getattr(self.runtime, "news_capital_platform_url", "https://capital.com/trading/platform"),
                    headless=getattr(self.runtime, "news_capital_playwright_headless", True),
                )
            )
        return collectors

    async def collect_run_now(self, instrument: str | None = None) -> dict[str, Any]:
        instrument = (instrument or getattr(self.runtime, "instrument", "XAUUSD")).upper()
        if not getattr(self.runtime, "news_collection_enabled", True):
            return {"status": "DISABLED", "collected": 0, "saved": 0}
        saved = 0
        duplicates = 0
        analyzed = 0
        errors: list[str] = []
        for collector in self.collectors:
            source = getattr(collector, "source_name", collector.__class__.__name__)
            try:
                items = await collector.collect(instrument)
                self.repository.record_source_success(source)
            except Exception as exc:
                self.repository.record_source_failure(source, str(exc))
                errors.append(f"{source}: {exc}")
                continue
            for item in items:
                item_id = self.save_news_item(item)
                if item_id is None:
                    duplicates += 1
                    continue
                saved += 1
                if self.should_analyze(item):
                    analysis = self.analyzer.analyze_news_item(item)
                    if analysis:
                        if self.repository.save_ai_analysis(analysis, news_item_id=item_id):
                            analyzed += 1
        state = self.aggregator.aggregate(instrument)
        return {
            "status": "OK" if not errors else "DEGRADED",
            "collected": saved + duplicates,
            "saved": saved,
            "duplicates": duplicates,
            "analyzed": analyzed,
            "errors": errors,
            "state": state.model_dump(mode="json"),
        }

    def save_news_item(self, item: NormalizedNewsItem) -> int | None:
        news_hash = generate_news_hash(item.title, item.source, item.instrument, item.published_at)
        before = len(self.repository.get_news_items(item.instrument, limit=1_000_000)) if getattr(self.repository, "_in_memory", False) else None
        item_id = self.repository.save_news_item(item, news_hash)
        if before is not None:
            after = len(self.repository.get_news_items(item.instrument, limit=1_000_000))
            if after == before:
                return None
        return item_id

    def manual_news(self, payload: dict[str, Any]) -> dict[str, Any]:
        instrument = str(payload.get("instrument") or getattr(self.runtime, "instrument", "XAUUSD")).upper()
        item = normalize_news_payload(payload, instrument, default_source="manual")
        item_id = self.repository.save_news_item(item, generate_news_hash(item.title, item.source, item.instrument, item.published_at))
        analysis_id = None
        if item_id and self.should_analyze(item):
            analysis = self.analyzer.analyze_news_item(item)
            if analysis:
                analysis_id = self.repository.save_ai_analysis(analysis, news_item_id=item_id)
        state = self.aggregator.aggregate(instrument)
        return {"id": item_id, "analysis_id": analysis_id, "state": state.model_dump(mode="json")}

    def manual_macro_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event = MacroEventModel.model_validate(payload)
        event_id = self.macro_ingestor.ingest_event(event)
        analysis_id = None
        if event_id and getattr(self.runtime, "news_ai_analysis_enabled", True):
            analysis = self.analyzer.analyze_macro_event(event, instrument=getattr(self.runtime, "instrument", "XAUUSD"))
            if analysis:
                analysis_id = self.repository.save_ai_analysis(analysis, macro_event_id=event_id)
        state = self.aggregator.aggregate(getattr(self.runtime, "instrument", "XAUUSD"))
        return {"id": event_id, "analysis_id": analysis_id, "state": state.model_dump(mode="json")}

    def update_macro_actual(self, event_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        actual = str(payload.get("actual_value") or payload.get("actual") or "")
        if not actual:
            return {"status": "ERROR", "message": "actual_value is required"}
        row = self.repository.update_macro_event_actual(event_id, actual)
        if not row:
            return {"status": "NOT_FOUND"}
        return {"status": "OK", "event": row}

    def risk_window(self, instrument: str | None = None) -> dict[str, Any]:
        events = self.repository.get_macro_events(limit=100)
        return current_risk_window(events)

    def dashboard_summary(self, instrument: str | None = None) -> dict[str, Any]:
        instrument = (instrument or getattr(self.runtime, "instrument", "XAUUSD")).upper()
        summary = self.repository.dashboard_summary(instrument)
        summary["risk_window"] = self.risk_window(instrument)
        summary["feature_flags"] = {
            "collection_enabled": getattr(self.runtime, "news_collection_enabled", True),
            "ai_analysis_enabled": getattr(self.runtime, "news_ai_analysis_enabled", True),
            "strategy_weight_enabled": getattr(self.runtime, "news_strategy_weight_enabled", False),
            "trade_block_enabled": getattr(self.runtime, "news_trade_block_enabled", False),
            "risk_reduction_enabled": getattr(self.runtime, "news_risk_reduction_enabled", False),
            "shadow_mode": getattr(self.runtime, "news_shadow_mode", True),
        }
        return summary

    def should_analyze(self, item: NormalizedNewsItem) -> bool:
        if not getattr(self.runtime, "news_ai_analysis_enabled", True):
            return False
        order = {"LOW": 1, "UNKNOWN": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        min_relevance = str(getattr(self.runtime, "news_min_relevance_to_analyze", "MEDIUM")).upper()
        return order.get(item.relevance, 1) >= order.get(min_relevance, 2)
