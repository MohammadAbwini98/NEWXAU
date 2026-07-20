# Phase 06 - Dashboard and Observability

## Goal

Add dashboard visibility for collected news, AI impact analysis, macro-event schedule, active news state, and strategy impact.

## Dashboard sections

Create a new dashboard page or panel:

```text
News Intelligence
```

Recommended sub-sections:

1. Active XAUUSD news state.
2. Latest related news.
3. AI impact analysis feed.
4. Upcoming macro events.
5. Current risk window.
6. Shadow-mode validation summary.
7. Source health.

## Active news state card

Show:

```text
Instrument: XAUUSD
Active bias: BUY / SELL / HOLD / NO_TRADE
Confidence: 0.72
News weight: 0.20
Action level: WEIGHT_ONLY / BLOCK_NEW_TRADES
Risk: MEDIUM/HIGH
Valid until: timestamp
Reason: short summary
```

Color/status idea:

```text
Green/positive   = BUY bias
Red/negative     = SELL bias
Gray             = Neutral
Orange           = High risk
Purple/alert     = Block new trades
```

Use whatever UI theme your dashboard already uses.

## Latest news table

Columns:

```text
Time
Source
Title
Event Type
Relevance
Analyzed?
AI Bias
Confidence
Action
```

Add filters:

```text
Instrument
Event type
Relevance
Source
Analyzed / not analyzed
Date range
```

## AI analysis details drawer

When clicking a row, show:

```text
Title
Source
Published time
Event type
AI direction
Trade bias
Confidence
Expected time window
Market session
Volatility expected
Risk level
Summary
Reasoning points
Raw JSON toggle
```

## Macro-event calendar panel

Show upcoming events:

```text
CPI
FOMC
NFP
Fed speeches
Other high-impact USD events
```

Columns:

```text
Scheduled time
Event type
Importance
Forecast
Previous
Actual
Risk window status
```

## Risk-window countdown

If a high-impact event is near:

```text
CPI in 22 minutes
New trades blocked from 30 minutes before until 15 minutes after release
```

Show:

```text
Before window start
Inside blocked window
Post-release wait window
Normal trading resumed
```

## Strategy impact visualization

For each signal, show:

```text
KRONOS score: 0.66
Technical score: 0.58
News score: 0.72
Final score before news: 0.62
Final score after news: 0.65
Decision: BUY allowed
```

This helps debug why a trade was allowed, reduced, or blocked.

## Source health panel

Show source status:

```text
Capital.com related news collector: OK / degraded / failed
RSS collector: OK / degraded / failed
Macro calendar collector: OK / degraded / failed
AI analyzer: OK / degraded / failed
Last successful collection time
Last error message
```

## Alerts

Add dashboard alerts for:

```text
High-impact event within 30 minutes
AI analyzer failing repeatedly
Capital.com session expired
News collector found critical war escalation
News state blocked new trades
News state conflicts with KRONOS
```

## Backend endpoints

```text
GET /api/news/dashboard/summary?instrument=XAUUSD
GET /api/news/items?instrument=XAUUSD&limit=50
GET /api/news/analysis?instrument=XAUUSD&limit=50
GET /api/news/state?instrument=XAUUSD
GET /api/news/macro-events?from=&to=
GET /api/news/sources/health
GET /api/news/validation/summary?instrument=XAUUSD
```

## Observability logs

Use structured logs:

```json
{
  "event": "news_ai_analysis_created",
  "instrument": "XAUUSD",
  "event_type": "CPI",
  "direction": "UP",
  "confidence": 0.72,
  "action_level": "WEIGHT_ONLY",
  "valid_until": "..."
}
```

## Metrics

Track:

```text
news_items_collected_total
news_items_deduplicated_total
news_ai_analysis_success_total
news_ai_analysis_failed_total
active_news_state_changes_total
news_trade_blocks_total
news_position_reductions_total
collector_failures_total
```

## Acceptance criteria

- Dashboard shows active news state.
- Dashboard shows latest news and AI impact.
- Dashboard shows upcoming CPI/FOMC/NFP/Fed events.
- Dashboard clearly explains why news affected or blocked a signal.
- Source health and errors are visible.
