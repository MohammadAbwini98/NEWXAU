# Phase 05 - News State and Strategy Weighting

## Goal

Convert individual AI news analyses into a single active `strategy_news_state` per instrument and allow the strategy engine to consume it safely.

## Core idea

Many news items can arrive during the day. The strategy should not read each item directly. It should read one aggregated state:

```text
XAUUSD current news state:
- active bias
- active confidence
- active risk level
- whether to reduce position size
- whether to block new trades
- valid until
```

## Aggregation inputs

Use active `news_ai_analysis` records where:

```text
instrument = XAUUSD
valid_until > now()
news_relevance in HIGH/CRITICAL or confidence >= configured threshold
```

## Aggregation logic

### Convert direction to numeric score

```text
UP      = +1.0
DOWN    = -1.0
NEUTRAL =  0.0
MIXED   =  0.0 with increased risk
UNKNOWN =  0.0
```

### Convert impact strength multiplier

```text
LOW     = 0.25
MEDIUM  = 0.50
HIGH    = 0.80
EXTREME = 1.00
```

### Individual news score

```text
news_score = direction_score * confidence * impact_multiplier
```

### Aggregate score

```text
active_news_score = weighted_average(active_news_scores)
```

Example interpretation:

```text
>= +0.30  => BUY bias
<= -0.30  => SELL bias
otherwise => HOLD/NEUTRAL
```

## Conflict handling

If active news is conflicting:

```text
Example:
- CPI analysis says gold down.
- War escalation says gold up.
```

Then:

```text
active_direction = MIXED
active_trade_bias = NO_TRADE or HOLD
risk_level = HIGH
should_reduce_position_size = true
possibly block new trades if volatility is HIGH/EXTREME
```

## Strategy integration formula

Normal state:

```text
final_score =
    kronos_score * 0.50
  + technical_strategy_score * 0.30
  + news_impact_score * 0.20
```

High-impact news state:

```text
final_score =
    kronos_score * 0.40
  + technical_strategy_score * 0.25
  + news_impact_score * 0.35
```

## Trade behavior rules

### News agrees with KRONOS

```text
KRONOS = BUY
News = BUY
News confidence >= 0.65
```

Action:

```text
- Allow trade if normal risk rules pass.
- Increase final score.
- Optional position multiplier: 1.05 to 1.15.
```

### News conflicts with KRONOS

```text
KRONOS = BUY
News = SELL
News confidence >= 0.70
```

Action:

```text
- Reduce final score.
- Reduce position size.
- Block trade if event is HIGH/CRITICAL and volatility is HIGH/EXTREME.
```

### High-impact unclear news

```text
News = MIXED or NEUTRAL
Volatility = HIGH/EXTREME
```

Action:

```text
- Block new trades temporarily.
- Manage existing trades only.
- Wait for one or two 5m candles after event.
```

### Low-relevance news

```text
relevance = LOW
```

Action:

```text
- Store for audit.
- No strategy impact.
```

## Position-size adjustment

Suggested multiplier rules:

| State | Position multiplier |
|---|---:|
| News agrees, medium confidence | 1.05 |
| News agrees, high confidence | 1.10 |
| News agrees, critical but volatile | 1.00 or lower |
| News conflicts | 0.50-0.75 |
| Mixed/high volatility | 0.00-0.50 |
| Block window | 0.00 for new entries |

Never exceed your global risk limits.

## Risk-engine integration

Risk engine must have final authority.

```text
if news_state.block_trading:
    reject_new_trade("Blocked by active news risk window")

if news_state.reduce_position_size:
    position_size *= configured_reduction_multiplier
```

## Feature flag stages

### Stage 1

```text
NEWS_STRATEGY_WEIGHT_ENABLED=false
NEWS_TRADE_BLOCK_ENABLED=false
```

Dashboard only.

### Stage 2

```text
NEWS_STRATEGY_WEIGHT_ENABLED=true
NEWS_TRADE_BLOCK_ENABLED=false
```

Weight only, no blocking.

### Stage 3

```text
NEWS_STRATEGY_WEIGHT_ENABLED=true
NEWS_TRADE_BLOCK_ENABLED=true
```

Allow blocking only around scheduled high-impact events.

### Stage 4

```text
Enable geopolitical/manual-review behavior.
```

## Audit fields to attach to every signal

Every generated signal should store:

```text
news_state_id
news_bias
news_confidence
news_weight_used
news_action_level
news_block_reason
final_score_before_news
final_score_after_news
```

## Acceptance criteria

- Strategy can read one active news state.
- News state expires automatically.
- Conflicting news increases risk instead of forcing bad direction.
- Feature flags can fully disable live impact.
- Each signal records how news affected it.
