# Phase 02 - News Source Collection

## Goal

Collect XAUUSD-relevant news from available sources, normalize it, deduplicate it, and store it in `news_items`.

## Important design note

Capital.com has official APIs for trading and market data, but the related-news panel may not be available through a documented official API. Therefore, implement source collection using a layered approach:

1. **Official API first** where available.
2. **Playwright collector** for Capital.com UI related news only if permitted and stable.
3. **Free/open fallback sources** such as RSS feeds or public news pages.

## Source priority

| Priority | Source | Purpose |
|---:|---|---|
| 1 | Capital.com official API | Prices, sessions, instruments, execution |
| 2 | Capital.com UI via Playwright | Related news extraction if no official news endpoint exists |
| 3 | Free RSS/public sources | Backup and wider macro/geopolitical coverage |
| 4 | Manual event/news injection | Emergency override from dashboard |

## Playwright session flow

### First run

```text
1. Launch browser in visible mode.
2. Open Capital.com platform.
3. User logs in manually.
4. Navigate to trading page.
5. User selects Gold / XAUUSD / NEWXAU.
6. Save browser storage state to secure local file.
```

Example storage path:

```text
storage/capital_com_session_state.json
```

Do not commit this file to Git.

### Normal run

```text
1. Launch Playwright with saved storage state.
2. Open Capital.com trading page.
3. Confirm active account is Demo or configured account.
4. Select XAUUSD/Gold instrument.
5. Open or read Related News panel.
6. Extract news cards.
7. Normalize fields.
8. Deduplicate and store.
```

## Extracted fields

Each news card should produce:

```json
{
  "instrument": "XAUUSD",
  "source": "Reuters News",
  "title": "Example title",
  "published_at": "2026-06-19T12:30:00Z",
  "collected_at": "2026-06-19T12:35:00Z",
  "url": null,
  "raw_text": "optional expanded text",
  "raw_payload": {},
  "event_type": "GENERAL_NEWS",
  "relevance": "UNKNOWN"
}
```

## News deduplication

Use:

```text
sha256(normalized_title + source + published_at + instrument)
```

If timestamp is missing:

```text
sha256(normalized_title + source + instrument)
```

## XAUUSD relevance filter

Classify as relevant when title/body contains terms such as:

```text
gold
XAUUSD
bullion
precious metals
US dollar
DXY
Treasury yields
Federal Reserve
Fed
interest rates
inflation
CPI
PPI
NFP
jobs report
unemployment
war
geopolitical
safe haven
central bank buying
```

Downweight or ignore:

```text
Ethereum-only news
Bitcoin-only news
Crypto-company news
Single-stock news
Unrelated IPO news
```

## Collector scheduling

Recommended intervals:

| Collector | Frequency |
|---|---:|
| Capital.com related news UI | Every 2-5 minutes |
| RSS/public news sources | Every 5-10 minutes |
| Manual refresh from dashboard | On demand |

Do not scrape too aggressively.

## Failure handling

The collector must handle:

- Login session expired.
- UI selector changed.
- Related news panel closed.
- Instrument selection failed.
- Duplicate news found.
- Network timeout.
- Empty related-news panel.

When a failure happens:

```text
1. Log the error.
2. Keep the service alive.
3. Mark source health as degraded.
4. Notify dashboard if repeated failures occur.
5. Do not affect trading if source is unavailable.
```

## Backend service contract

Create a collector interface:

```python
class NewsCollector:
    def collect(self, instrument: str) -> list[NormalizedNewsItem]:
        pass
```

Implement:

```text
CapitalComRelatedNewsCollector
RssNewsCollector
ManualNewsCollector
```

## API endpoints

```text
POST /api/news/collect/run-now
GET  /api/news/sources/health
POST /api/news/manual
```

## Acceptance criteria

- The collector can store new news items.
- Duplicate news is not inserted twice.
- XAUUSD relevance is assigned at least as UNKNOWN, LOW, MEDIUM, or HIGH.
- Collector failure does not crash the trading system.
- Collected news appears through `GET /api/news/items`.
