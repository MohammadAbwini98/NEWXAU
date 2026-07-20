# Phase 08 - Controlled Live Rollout

## Goal

Gradually allow the news feature to affect live trading after shadow-mode validation.

## Rollout stages

### Stage 0 - Dashboard only

```text
NEWS_COLLECTION_ENABLED=true
NEWS_AI_ANALYSIS_ENABLED=true
NEWS_STRATEGY_WEIGHT_ENABLED=false
NEWS_TRADE_BLOCK_ENABLED=false
NEWS_SHADOW_MODE=true
```

Effect:

```text
No trading impact.
```

### Stage 1 - Scheduled event warning only

```text
Enable event countdown and dashboard warnings.
```

Effect:

```text
No automated blocking.
User can manually avoid trading.
```

### Stage 2 - Reduce size around high-impact events

```text
NEWS_STRATEGY_WEIGHT_ENABLED=false
NEWS_TRADE_BLOCK_ENABLED=false
NEWS_RISK_REDUCTION_ENABLED=true
```

Effect:

```text
During CPI/FOMC/NFP/Fed speech risk windows:
- reduce position size by 25%-50%
- no direction bias yet
```

### Stage 3 - Block new trades around scheduled high-impact events

```text
NEWS_TRADE_BLOCK_ENABLED=true
```

Effect:

```text
Block new entries during configured windows.
Existing trades are still managed.
```

### Stage 4 - Strategy weighting

```text
NEWS_STRATEGY_WEIGHT_ENABLED=true
```

Effect:

```text
News score participates in final signal score.
Maximum normal news weight: 0.10-0.20
Maximum high-impact news weight: 0.20-0.35
```

### Stage 5 - Geopolitical risk controls

```text
Enable war-escalation risk behavior.
```

Effect:

```text
High/Extreme war escalation can:
- reduce risk
- block new trades
- request manual review
```

## Live safety rules

Never allow:

```text
- AI news alone to open a trade.
- News to bypass max daily loss.
- News to bypass max open positions.
- News to bypass spread/slippage filters.
- News to increase position above global risk limits.
```

## Recommended initial limits

```yaml
news_live_rollout:
  max_news_weight_normal: 0.10
  max_news_weight_high_impact: 0.20
  max_position_multiplier: 1.05
  default_conflict_size_multiplier: 0.50
  block_new_trades_on_extreme_risk: true
  require_kronos_agreement_for_size_increase: true
```

## Manual override controls

Dashboard should include:

```text
Disable news impact for today
Disable trade blocking
Force info-only mode
Manually clear active news state
Manually add high-risk event
```

All manual overrides must be audited.

## Live monitoring checklist

During first live week, review daily:

```text
News items collected
AI analyses generated
Signals affected by news
Trades blocked by news
Trades reduced by news
Any missed trades due to news
Any bad trades that news failed to block
Collector/session errors
AI output errors
```

## Rollback plan

At any time, set:

```text
NEWS_STRATEGY_WEIGHT_ENABLED=false
NEWS_TRADE_BLOCK_ENABLED=false
NEWS_RISK_REDUCTION_ENABLED=false
NEWS_SHADOW_MODE=true
```

This returns the system to observation-only mode.

## Acceptance criteria

- News impact can be enabled/disabled without redeploying.
- Strategy logs every news adjustment.
- Risk engine remains final authority.
- Rollback to shadow mode works immediately.
- No trade is opened solely from AI news bias.
