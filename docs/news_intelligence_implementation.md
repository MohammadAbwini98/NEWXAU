# News Intelligence Implementation Report

## Summary

Implemented the XAUUSD News Intelligence layer across collection, normalization, strict analysis validation, persistence, aggregation, rollout flags, API endpoints, dashboard visibility, and focused tests.

The feature defaults to safe shadow/dashboard behavior. News analysis cannot execute trades, cannot bypass the risk engine, and does not affect live strategy scoring or trade blocking unless the rollout flags are explicitly enabled.

## Main Files Changed

- `src/gold_signal_system/news_intelligence/models.py`
- `src/gold_signal_system/news_intelligence/collectors.py`
- `src/gold_signal_system/news_intelligence/ai_analyzer.py`
- `src/gold_signal_system/news_intelligence/repository.py`
- `src/gold_signal_system/news_intelligence/macro_events.py`
- `src/gold_signal_system/news_intelligence/strategy_integration.py`
- `src/gold_signal_system/news_intelligence/service.py`
- `src/gold_signal_system/news_intelligence/validation.py`
- `src/gold_signal_system/api.py`
- `src/gold_signal_system/pipeline.py`
- `src/gold_signal_system/recommendation_builder.py`
- `src/gold_signal_system/strategy_brain.py`
- `src/gold_signal_system/config.py`
- `src/gold_signal_system/dashboard_static/news.html`
- `db/009_news_intelligence.sql`
- `tests/test_news_intelligence.py`

## New/Extended Tables

- `news_items`
- `macro_events`
- `news_ai_analysis`
- `strategy_news_state`
- `news_impact_validation`
- `news_source_health`

All changes are additive. No existing trading/execution tables are dropped or truncated.

## API Endpoints

- `GET /api/news/dashboard/summary?instrument=XAUUSD`
- `GET /api/news/items?instrument=XAUUSD&limit=50`
- `GET /api/news/analysis?instrument=XAUUSD&limit=50`
- `GET /api/news/state?instrument=XAUUSD`
- `GET /api/news/macro-events?from=&to=&type=`
- `GET /api/news/risk-window?instrument=XAUUSD`
- `GET /api/news/sources/health`
- `POST /api/news/collect/run-now`
- `POST /api/news/manual`
- `POST /api/news/macro-events/manual`
- `PUT /api/news/macro-events/{id}/actual`
- `GET /api/news/validation/summary?instrument=XAUUSD`

## Feature Flags

Safe defaults:

```text
ENABLE_NEWS_INTELLIGENCE=1
NEWS_COLLECTION_ENABLED=1
NEWS_AI_ANALYSIS_ENABLED=1
NEWS_DASHBOARD_ENABLED=1
NEWS_SHADOW_MODE=1
NEWS_STRATEGY_WEIGHT_ENABLED=0
NEWS_TRADE_BLOCK_ENABLED=0
NEWS_RISK_REDUCTION_ENABLED=0
```

Optional collection/provider settings:

```text
NEWS_RSS_URLS=https://example.com/rss,https://example.com/feed.xml
NEWS_CAPITAL_RELATED_ENABLED=0
NEWS_CAPITAL_SESSION_STATE_PATH=storage/capital_com_session_state.json
NEWS_CAPITAL_EXPORTED_NEWS_PATH=runtime/news/capital_related_news.json
NEWS_AI_PROVIDER=rules
NEWS_AI_PROVIDER=openai
NEWS_AI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=...
```

## Rollout

Dashboard/shadow only:

```text
NEWS_STRATEGY_WEIGHT_ENABLED=0
NEWS_TRADE_BLOCK_ENABLED=0
NEWS_RISK_REDUCTION_ENABLED=0
NEWS_SHADOW_MODE=1
```

Weight only:

```text
NEWS_STRATEGY_WEIGHT_ENABLED=1
NEWS_TRADE_BLOCK_ENABLED=0
```

Scheduled-event blocking:

```text
NEWS_TRADE_BLOCK_ENABLED=1
```

Immediate rollback:

```text
NEWS_STRATEGY_WEIGHT_ENABLED=0
NEWS_TRADE_BLOCK_ENABLED=0
NEWS_RISK_REDUCTION_ENABLED=0
NEWS_SHADOW_MODE=1
```

## Known Limitations

- Capital.com related-news UI collection is optional and disabled by default. It requires Playwright and a user-created browser storage-state file after verifying platform terms.
- Stable free macro-calendar APIs vary by provider; manual macro entry is implemented and safe for the first release.
- If no external AI provider is configured, the analyzer uses deterministic conservative rules rather than mock data.
- Full historical news backtesting requires accumulated historical news; forward shadow validation is implemented.

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_news_intelligence.py -q
.\.venv\Scripts\python.exe -m compileall src\gold_signal_system\news_intelligence src\gold_signal_system\api.py src\gold_signal_system\pipeline.py
```
