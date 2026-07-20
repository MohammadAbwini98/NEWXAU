# KRONOS XAUUSD News Intelligence Feature - Master Implementation Plan

## Objective

Build a news-intelligence layer for the KRONOS XAUUSD trading system that collects market-moving news and macro events, analyzes their likely impact on XAUUSD, and feeds a structured news score into the strategy/risk engine.

This feature must support:

- Capital.com related-news collection where technically and legally possible.
- External free/open news and economic calendar sources where available.
- CPI, FOMC, NFP, major Fed speeches, and geopolitical/war escalation events.
- AI-based impact classification with strict structured JSON output.
- Shadow-mode validation before live trading influence.
- Strategy weighting, risk reduction, trade blocking, and dashboard visibility.

## Core principle

News should not directly execute trades. News should act as a context and risk layer.

Recommended responsibility split:

```text
KRONOS model       = price prediction brain
Strategy engine    = trading decision brain
News AI engine     = context, risk, and impact brain
Risk engine        = final permission and sizing brain
Execution engine   = broker integration layer
```

## High-level architecture

```text
News Sources
  ├─ Capital.com related news collector
  ├─ Economic calendar collector
  ├─ Fed speech / central-bank event collector
  ├─ Geopolitical risk collector
  └─ Optional free RSS/news feeds
        ↓
News Normalizer
        ↓
Deduplication + Relevance Filter
        ↓
AI News Impact Analyzer
        ↓
PostgreSQL News Store
        ↓
News State Aggregator
        ↓
Strategy + Risk Engine
        ↓
Dashboard + Audit Trail
```

## Event types to support

| Event type | Importance for XAUUSD | Typical behavior |
|---|---:|---|
| CPI | Very high | Moves inflation and rate expectations |
| FOMC | Very high | Moves USD, yields, and gold direction |
| NFP | Very high | Moves labor-market and rate expectations |
| Major Fed speeches | High | Can change market expectations intraday |
| War escalation | High/Very high | Can trigger safe-haven demand |
| General gold news | Medium/High | Depends on relevance |
| Crypto/equity-only news | Low | Usually ignore unless risk sentiment impact is clear |

## Global implementation phases

1. **Phase 01 - Foundations and schema**
2. **Phase 02 - News source collection**
3. **Phase 03 - Economic calendar and macro events**
4. **Phase 04 - AI impact analyzer**
5. **Phase 05 - News state and strategy weighting**
6. **Phase 06 - Dashboard and observability**
7. **Phase 07 - Shadow-mode validation and backtesting**
8. **Phase 08 - Controlled live rollout**
9. **Phase 09 - Hardening, safety, and operations**

## Recommended first release behavior

The first release should only:

- Collect news.
- Analyze news with AI.
- Store structured results.
- Show the result in the dashboard.
- Run in shadow mode.

It should not affect real trades until the system has enough validation data.

## News action levels

| Action level | Meaning | Trading effect |
|---|---|---|
| INFO_ONLY | Store and display only | No trading impact |
| WEIGHT_ONLY | Adjust final score | No hard blocking |
| RISK_REDUCE | Reduce position size | Lower size/risk |
| BLOCK_NEW_TRADES | Pause new entries | Existing trades can still be managed |
| MANUAL_REVIEW | Require manual approval | Used for extreme or uncertain events |

## Suggested final score formula

Normal market:

```text
final_score =
    kronos_score * 0.50
  + technical_strategy_score * 0.30
  + news_impact_score * 0.20
```

High-impact macro/news window:

```text
final_score =
    kronos_score * 0.40
  + technical_strategy_score * 0.25
  + news_impact_score * 0.35
```

Do not allow the news score to become 100% of the decision unless you intentionally enable a separate manual news-trading mode.

## Success criteria

The feature is successful when:

- It detects CPI, FOMC, NFP, Fed speeches, and war-escalation events.
- It produces consistent structured AI output.
- The dashboard shows active news bias and risk status.
- The strategy can consume news state safely.
- Shadow-mode statistics prove whether news signals improve or harm performance.
- No live trade is opened solely because of a news article.
