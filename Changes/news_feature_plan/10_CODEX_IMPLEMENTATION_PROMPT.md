# Codex Prompt - Implement KRONOS XAUUSD News Intelligence Feature

## Role

You are a senior full-stack trading-system engineer. Review the entire KRONOS codebase before making changes. Pay special attention to existing services, strategy engine, signal generation, risk engine, database access, dashboard APIs, background jobs, and configuration style.

## Goal

Implement a phased News Intelligence feature for XAUUSD that collects relevant news and macro events, analyzes them with an AI model, stores structured results, displays them on the dashboard, and later allows controlled strategy weighting/risk blocking through feature flags.

## Required documents to follow

Use the following implementation plan files as the source of truth:

```text
00_NEWS_FEATURE_MASTER_PLAN.md
01_PHASE_FOUNDATIONS_AND_SCHEMA.md
02_PHASE_NEWS_SOURCE_COLLECTION.md
03_PHASE_ECONOMIC_CALENDAR_AND_MACRO_EVENTS.md
04_PHASE_AI_IMPACT_ANALYZER.md
05_PHASE_NEWS_STATE_AND_STRATEGY_WEIGHTING.md
06_PHASE_DASHBOARD_AND_OBSERVABILITY.md
07_PHASE_SHADOW_VALIDATION_AND_BACKTESTING.md
08_PHASE_CONTROLLED_LIVE_ROLLOUT.md
09_PHASE_HARDENING_SAFETY_AND_OPERATIONS.md
```

## Implementation requirements

### 1. Foundations

- Add database migrations/tables for:
  - `news_items`
  - `macro_events`
  - `news_ai_analysis`
  - `strategy_news_state`
  - `news_impact_validation`
- Add models/entities/repositories according to existing project style.
- Add configuration section `news_intelligence`.
- Add feature flags:
  - `NEWS_COLLECTION_ENABLED`
  - `NEWS_AI_ANALYSIS_ENABLED`
  - `NEWS_STRATEGY_WEIGHT_ENABLED`
  - `NEWS_TRADE_BLOCK_ENABLED`
  - `NEWS_DASHBOARD_ENABLED`
  - `NEWS_SHADOW_MODE`

### 2. News collection

- Implement a collector interface.
- Implement placeholder/adaptable collectors:
  - `CapitalComRelatedNewsCollector` using Playwright session state if compatible with project.
  - `RssNewsCollector` or generic public-source collector.
  - `ManualNewsCollector` through API.
- Add deduplication using a stable hash.
- Add XAUUSD relevance classification.
- Collector failures must not crash trading.

### 3. Macro events

- Add support for event types:
  - CPI
  - FOMC rate decision
  - FOMC minutes
  - NFP
  - Fed speech
  - War escalation
  - Geopolitical risk
- Add risk-window calculation around high-impact events.
- Add manual macro-event API for entering events if no stable free calendar source exists.

### 4. AI analyzer

- Implement AI analysis service that accepts news or macro events and returns strict JSON.
- Add output validation and enum checks.
- Save valid outputs to `news_ai_analysis`.
- Retry invalid/failed analysis safely.
- Do not allow AI analyzer to execute trades.

### 5. Strategy integration

- Implement `strategy_news_state` aggregation.
- Strategy should read only the active aggregated state, not raw news.
- Start with shadow mode by default.
- Add audit fields to each generated signal:
  - `news_state_id`
  - `news_bias`
  - `news_confidence`
  - `news_weight_used`
  - `news_action_level`
  - `news_block_reason`
  - `final_score_before_news`
  - `final_score_after_news`
- Risk engine must remain final authority.
- News must never open a trade by itself.

### 6. Dashboard/API

Add API endpoints:

```text
GET  /api/news/dashboard/summary?instrument=XAUUSD
GET  /api/news/items?instrument=XAUUSD&limit=50
GET  /api/news/analysis?instrument=XAUUSD&limit=50
GET  /api/news/state?instrument=XAUUSD
GET  /api/news/macro-events?from=&to=&type=
GET  /api/news/risk-window?instrument=XAUUSD
GET  /api/news/sources/health
POST /api/news/collect/run-now
POST /api/news/manual
POST /api/news/macro-events/manual
PUT  /api/news/macro-events/{id}/actual
GET  /api/news/validation/summary?instrument=XAUUSD
```

Dashboard should show:

- Active XAUUSD news state.
- Latest related news.
- AI impact feed.
- Upcoming CPI/FOMC/NFP/Fed events.
- Current risk window.
- Source health.
- Shadow-mode validation summary.

### 7. Shadow validation

- Evaluate AI direction against future XAUUSD price movement at:
  - 5m
  - 15m
  - 30m
  - 60m
  - 240m
- Store results in `news_impact_validation`.
- Add summary stats by event type and confidence bucket.

## Safety requirements

- Default mode must be shadow mode.
- Live trade impact must be disabled by default.
- News cannot bypass risk limits.
- Expired news state must be ignored.
- Collector or AI failures must not block trading unless a valid active high-risk state already exists.
- Add rollback flags to return to baseline strategy immediately.

## Testing requirements

Add tests for:

- Deduplication.
- Relevance classification.
- AI JSON validation.
- Macro risk-window calculation.
- News-state aggregation.
- Strategy weighting.
- Stale state expiry.
- Feature flags.
- API endpoints.

## Deliverables

1. Code changes.
2. Database migrations.
3. Configuration updates.
4. API endpoints.
5. Dashboard updates.
6. Tests.
7. A markdown implementation report describing:
   - Files changed.
   - New tables.
   - New endpoints.
   - Feature flags.
   - How to run collectors.
   - How to enable/disable live impact.
   - Known limitations.

## Final instruction

Implement this feature incrementally and safely. Do not enable live trading influence by default. After implementation, run tests and provide a concise report with any failures, skipped items, or assumptions.
