from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree

import requests

from .models import EventType, NewsRelevance, NormalizedNewsItem

logger = logging.getLogger(__name__)


XAUUSD_HIGH_KEYWORDS = (
    "gold",
    "xauusd",
    "bullion",
    "precious metal",
    "precious metals",
    "fomc",
    "federal reserve",
    "fed ",
    "cpi",
    "nfp",
    "nonfarm",
    "non-farm",
    "payroll",
)
XAUUSD_MEDIUM_KEYWORDS = (
    "us dollar",
    "dxy",
    "treasury yield",
    "treasury yields",
    "interest rate",
    "interest rates",
    "inflation",
    "ppi",
    "jobless claims",
    "retail sales",
    "ism",
    "safe haven",
    "geopolitical",
    "war",
    "central bank buying",
)
LOW_RELEVANCE_ONLY = (
    "ethereum",
    "bitcoin",
    "crypto exchange",
    "crypto company",
    "ipo",
    "single stock",
)
WAR_KEYWORDS = (
    "missile attack",
    "military strike",
    "invasion",
    "retaliation",
    "escalation",
    "ceasefire collapse",
    "regional conflict",
    "nato emergency",
    "un security council",
    "sanctions escalation",
)


def _normalized_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def generate_news_hash(title: str, source: str, instrument: str, published_at: datetime | None = None) -> str:
    parts = [_normalized_title(title), source.strip().lower(), instrument.strip().upper()]
    if published_at is not None:
        parts.append(published_at.astimezone(UTC).replace(microsecond=0).isoformat())
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def classify_event_type(title: str, text: str | None = None) -> str:
    content = f"{title} {text or ''}".lower()
    if any(word in content for word in WAR_KEYWORDS):
        return EventType.WAR_ESCALATION.value
    if "fomc" in content and "minute" in content:
        return EventType.FOMC_MINUTES.value
    if "fomc" in content or "rate decision" in content or "fed decision" in content:
        return EventType.FOMC_RATE_DECISION.value
    if "cpi" in content or "consumer price" in content:
        return EventType.CPI.value
    if "nonfarm" in content or "non-farm" in content or "nfp" in content or "payroll" in content:
        return EventType.NFP.value
    if "fed" in content and any(word in content for word in ("speech", "speaks", "remarks", "powell")):
        return EventType.FED_SPEECH.value
    if "geopolitical" in content or "safe haven" in content:
        return EventType.GEOPOLITICAL_RISK.value
    if "ppi" in content or "producer price" in content:
        return EventType.PPI.value
    if "jobless claims" in content:
        return EventType.JOBLESS_CLAIMS.value
    if "retail sales" in content:
        return EventType.RETAIL_SALES.value
    if "ism" in content or "pmi" in content:
        return EventType.ISM_PMI.value
    if any(word in content for word in ("gold", "bullion", "xauusd")):
        return EventType.GENERAL_GOLD_NEWS.value
    return EventType.UNKNOWN.value


def classify_relevance(title: str, text: str | None = None) -> NewsRelevance:
    content = f"{title} {text or ''}".lower()
    if any(word in content for word in LOW_RELEVANCE_ONLY) and not any(word in content for word in XAUUSD_HIGH_KEYWORDS + XAUUSD_MEDIUM_KEYWORDS):
        return NewsRelevance.LOW
    if any(word in content for word in WAR_KEYWORDS):
        return NewsRelevance.CRITICAL
    if any(word in content for word in XAUUSD_HIGH_KEYWORDS):
        return NewsRelevance.HIGH
    if any(word in content for word in XAUUSD_MEDIUM_KEYWORDS):
        return NewsRelevance.MEDIUM
    return NewsRelevance.UNKNOWN


def normalize_news_payload(payload: dict[str, Any], instrument: str, default_source: str = "manual") -> NormalizedNewsItem:
    title = str(payload.get("title") or payload.get("headline") or "").strip()
    raw_text = payload.get("raw_text") or payload.get("description") or payload.get("summary") or payload.get("body")
    published = payload.get("published_at") or payload.get("published") or payload.get("date")
    published_at = _parse_datetime(published)
    event_type = str(payload.get("event_type") or classify_event_type(title, str(raw_text or ""))).upper()
    relevance = str(payload.get("relevance") or classify_relevance(title, str(raw_text or "")).value).upper()
    return NormalizedNewsItem(
        instrument=str(payload.get("instrument") or instrument).upper(),
        source=str(payload.get("source") or default_source),
        title=title,
        published_at=published_at,
        collected_at=datetime.now(tz=UTC),
        url=payload.get("url"),
        raw_text=str(raw_text) if raw_text is not None else None,
        raw_payload=payload,
        event_type=event_type,
        relevance=relevance,
    )


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except Exception:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class NewsCollector:
    source_name = "unknown"

    async def collect(self, instrument: str) -> list[NormalizedNewsItem]:
        raise NotImplementedError


class RssNewsCollector(NewsCollector):
    source_name = "rss"

    def __init__(self, urls: list[str] | None = None, timeout_seconds: float = 10.0) -> None:
        self.urls = [url.strip() for url in urls or [] if url.strip()]
        self.timeout_seconds = timeout_seconds

    async def collect(self, instrument: str) -> list[NormalizedNewsItem]:
        if not self.urls:
            return []
        return await asyncio.to_thread(self._collect_sync, instrument)

    def _collect_sync(self, instrument: str) -> list[NormalizedNewsItem]:
        items: list[NormalizedNewsItem] = []
        for url in self.urls:
            try:
                response = requests.get(url, timeout=self.timeout_seconds, headers={"User-Agent": "NEWXAU-NewsIntelligence/1.0"})
                response.raise_for_status()
                items.extend(self._parse_feed(response.text, instrument, url))
            except Exception as exc:
                logger.warning("RSS news collection failed for %s: %s", url, exc)
        return items

    def _parse_feed(self, xml_text: str, instrument: str, feed_url: str) -> list[NormalizedNewsItem]:
        root = ElementTree.fromstring(xml_text)
        parsed: list[NormalizedNewsItem] = []
        channel_title = root.findtext("./channel/title") or root.findtext("./{http://www.w3.org/2005/Atom}title") or "rss"
        rss_items = root.findall("./channel/item")
        atom_items = root.findall("./{http://www.w3.org/2005/Atom}entry")
        for item in rss_items:
            title = item.findtext("title") or ""
            if not title.strip():
                continue
            description = item.findtext("description")
            link = item.findtext("link")
            published = item.findtext("pubDate")
            payload = {
                "source": channel_title,
                "title": title,
                "description": description,
                "url": link,
                "published_at": published,
                "feed_url": feed_url,
            }
            parsed.append(normalize_news_payload(payload, instrument, default_source=channel_title))
        for item in atom_items:
            title = item.findtext("{http://www.w3.org/2005/Atom}title") or ""
            if not title.strip():
                continue
            summary = item.findtext("{http://www.w3.org/2005/Atom}summary")
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            payload = {
                "source": channel_title,
                "title": title,
                "description": summary,
                "url": link_node.attrib.get("href") if link_node is not None else None,
                "published_at": item.findtext("{http://www.w3.org/2005/Atom}updated") or item.findtext("{http://www.w3.org/2005/Atom}published"),
                "feed_url": feed_url,
            }
            parsed.append(normalize_news_payload(payload, instrument, default_source=channel_title))
        return parsed


class ManualNewsCollector(NewsCollector):
    source_name = "manual"

    async def collect(self, instrument: str) -> list[NormalizedNewsItem]:
        return []


class CapitalComRelatedNewsCollector(NewsCollector):
    source_name = "capital.com.related_news"

    def __init__(
        self,
        session_state_path: str | None = None,
        exported_news_path: str | None = None,
        platform_url: str = "https://capital.com/trading/platform",
        headless: bool = True,
    ) -> None:
        self.session_state_path = session_state_path
        self.exported_news_path = exported_news_path
        self.platform_url = platform_url
        self.headless = headless

    async def collect(self, instrument: str) -> list[NormalizedNewsItem]:
        exported = self._collect_from_exported_json(instrument)
        if exported:
            return exported
        if self.session_state_path:
            return await self._collect_with_playwright(instrument)
        return []

    def _collect_from_exported_json(self, instrument: str) -> list[NormalizedNewsItem]:
        if not self.exported_news_path:
            return []
        path = Path(self.exported_news_path)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                return []
            return [normalize_news_payload(row, instrument, default_source="Capital.com") for row in rows if isinstance(row, dict)]
        except Exception as exc:
            logger.warning("Capital.com exported news read failed: %s", exc)
            return []

    async def _collect_with_playwright(self, instrument: str) -> list[NormalizedNewsItem]:
        try:
            from playwright.async_api import async_playwright
        except Exception:
            logger.info("Playwright is not installed; Capital.com related-news collector is disabled.")
            return []

        state_path = Path(self.session_state_path or "")
        if not state_path.exists():
            logger.info("Capital.com Playwright storage state not found at %s.", state_path)
            return []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(storage_state=str(state_path))
            page = await context.new_page()
            try:
                await page.goto(self.platform_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
                cards = await page.locator("text=/Gold|XAUUSD|bullion|Fed|CPI|FOMC/i").all()
                items: list[NormalizedNewsItem] = []
                seen: set[str] = set()
                for card in cards[:40]:
                    text = (await card.inner_text(timeout=1000)).strip()
                    title = re.sub(r"\s+", " ", text).strip()
                    if len(title) < 12 or title in seen:
                        continue
                    seen.add(title)
                    items.append(
                        normalize_news_payload(
                            {
                                "source": "Capital.com",
                                "title": title[:300],
                                "raw_text": title,
                                "published_at": None,
                                "url": None,
                            },
                            instrument,
                            default_source="Capital.com",
                        )
                    )
                return items
            finally:
                await context.close()
                await browser.close()
