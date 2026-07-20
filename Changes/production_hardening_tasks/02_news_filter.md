# Task 02 — News Filter Production Hardening

## Goal

Upgrade the current manual/mock-capable news provider into a production-ready provider architecture.

The Strategy Brain must support real, manual, and mock news providers without knowing which one is active.

## Required Provider Design

Create or improve the following abstraction:

```text
INewsProvider
├── MockNewsProvider
├── ManualNewsProvider
└── RealEconomicCalendarProvider
```

The active provider must be selected by configuration.

Example:

```json
{
  "NewsProvider": {
    "Mode": "Manual",
    "BlockBeforeMinutes": 30,
    "BlockAfterMinutes": 30
  }
}
```

## Required Supported Events

The news filter must support high-impact Gold/XAUUSD events, especially USD events:

- CPI
- PPI
- NFP
- FOMC
- Fed speeches
- Interest rate decisions
- Unemployment data
- GDP
- Core PCE
- US dollar events
- Geopolitical/manual emergency events

## Event Schema

Each news event should include:

```json
{
  "event_id": "string",
  "title": "US CPI",
  "currency": "USD",
  "impact": "HIGH",
  "event_time": "datetime",
  "block_before_minutes": 30,
  "block_after_minutes": 30,
  "source": "manual/mock/real",
  "is_active": true
}
```

## Strategy Brain Integration

The Strategy Brain must apply news rules before final recommendation.

Required outcomes:

```text
BLOCKED_BY_NEWS
CONFIDENCE_REDUCED_BY_NEWS
NEWS_SPIKE_MODE
```

Example logic:

```text
If current time is within block_before/block_after window of high-impact USD news:
    block normal signals or reduce confidence depending on configuration.
```

## Dashboard Requirements

Add dashboard visibility for:

- Upcoming high-impact events
- Current news block status
- Why a signal was blocked by news
- Minutes before/after event
- Active provider mode: Mock / Manual / Real

## Database Requirements

Persist:

- News events
- Provider source
- Signal news snapshot
- Blocked reason if signal blocked by news

## Acceptance Criteria

- Strategy Brain reads news state through `INewsProvider`.
- Mock/manual/real provider modes are configurable.
- News-blocked signals include clear reasons.
- Dashboard shows news status.
- Tests cover news-blocking behavior.
