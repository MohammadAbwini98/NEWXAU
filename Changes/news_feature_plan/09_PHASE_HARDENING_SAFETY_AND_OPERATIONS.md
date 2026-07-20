# Phase 09 - Hardening, Safety, and Operations

## Goal

Make the news feature reliable, safe, observable, and maintainable for long-term use.

## Reliability requirements

The trading system must continue working if:

```text
Capital.com related-news UI changes
Playwright collector fails
AI analyzer returns invalid JSON
Economic calendar source is unavailable
News source produces duplicate or delayed news
Network connection fails
Database insert fails temporarily
```

## Safety defaults

If the news system is unhealthy:

```text
- Do not block trades because of stale news.
- Do not use stale news weights.
- Do not increase position size.
- Fall back to baseline KRONOS + strategy behavior.
- Show degraded status in dashboard.
```

## Stale state handling

If `valid_until < now()`:

```text
- Clear active news bias.
- Set action level to INFO_ONLY or NONE.
- Do not use expired confidence.
```

If collector has not succeeded recently:

```text
- Mark collector degraded.
- Do not assume no news exists.
- Dashboard should warn: news source stale.
```

## Security

Do not store credentials in code.

Protect:

```text
Capital.com API key
Capital.com session tokens
Playwright storage state
OpenAI/API keys
Database credentials
```

Use:

```text
.env files outside Git
secret manager if available
restricted file permissions
separate demo/live configuration
```

## Compliance and terms

Before using Playwright to extract Capital.com UI related news, verify that your intended use does not violate platform terms.

Safer design:

```text
- Use official APIs where available.
- Use RSS/open sources for news where possible.
- Treat UI scraping as optional and replaceable.
```

## Rate limits

Implement throttling:

```text
Playwright collector: every 2-5 minutes
RSS/news collector: every 5-10 minutes
AI analyzer: only new relevant items
Economic calendar: every 6 hours, more often on event days
```

## Testing plan

### Unit tests

```text
News normalization
Deduplication hashing
Relevance classification
AI JSON validation
Macro risk window calculation
News state aggregation
Strategy weighting logic
```

### Integration tests

```text
Collector -> DB insert
News item -> AI analyzer -> DB insert
Macro event -> risk window -> strategy state
News state -> signal calculation
Dashboard API response
```

### Failure tests

```text
Invalid AI JSON
Collector timeout
Expired Playwright session
Duplicate news
Missing timestamp
Conflicting news
Stale active state
Database unavailable
```

## Logging standards

Every important event should include:

```text
instrument
event_type
source
news_item_id
analysis_id
action_level
confidence
valid_until
feature_flags
```

## Operational runbook

### If Capital.com session expires

```text
1. Dashboard shows collector degraded.
2. Run manual login flow.
3. Save new storage state.
4. Restart collector.
5. Confirm latest related news appears.
```

### If AI analyzer fails

```text
1. Check API key/limits.
2. Inspect invalid JSON examples.
3. Retry failed analyses.
4. Keep trading in baseline mode.
```

### If news blocks too many trades

```text
1. Disable NEWS_TRADE_BLOCK_ENABLED.
2. Keep dashboard/shadow mode running.
3. Review validation reports.
4. Adjust risk windows and thresholds.
```

### If news causes bad live decisions

```text
1. Roll back to shadow mode immediately.
2. Export affected signal/trade audit logs.
3. Compare final_score_before_news vs final_score_after_news.
4. Lower max news weight.
5. Require higher confidence or KRONOS agreement.
```

## Production readiness checklist

```text
[ ] Feature flags implemented
[ ] Rollback tested
[ ] AI JSON validation implemented
[ ] Stale state cleanup implemented
[ ] Dashboard health panel implemented
[ ] News state audit fields attached to signals
[ ] Shadow validation report implemented
[ ] Manual override implemented
[ ] Secrets not committed
[ ] Playwright session file ignored by Git
[ ] Strategy never trades from news alone
```

## Acceptance criteria

- The system degrades safely.
- News state never remains active after expiry.
- Operators can disable news influence instantly.
- All news-driven trade changes are auditable.
- Tests cover collector, AI, state aggregation, and strategy integration.
