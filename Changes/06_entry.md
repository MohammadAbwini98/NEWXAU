# 06 - Entry, Stop Loss, and Take Profit Engine

## Document Map

- [01 - Overview](01_overview.md)
- [02 - Phases](02_phases.md)
- [03 - Models](03_models.md)
- [04 - Indicators](04_indicators.md)
- [05 - Strategy](05_strategy.md)
- [06 - Entry / SL / TP](06_entry.md)
- [07 - Risk](07_risk.md)
- [08 - Dashboard](08_dashboard.md)
- [09 - Database](09_database.md)
- [10 - Tasks](10_tasks.md)

## Goal

Convert model and strategy direction into a tradable plan:

```text
Entry price
Stop loss
Take profit 1
Take profit 2
Take profit 3
Risk/reward
Signal expiry
```

---

## Entry Types

| Entry Type | Use When | Risk |
|---|---|---|
| MARKET | Strong momentum and models agree | Higher |
| LIMIT_PULLBACK | Trend is valid but price is extended | Lower |
| BREAKOUT | Price breaks key level with confirmation | Medium |
| RETEST | Breakout happened and price retests level | Lower |
| REVERSAL | Price rejects major support/resistance | Higher |

---

## Market Entry

Use when:

```text
Model agreement is strong
Momentum is active
Spread is acceptable
ATR supports movement
Price is not too close to resistance/support
```

Example:

```json
{
  "entry_type": "MARKET",
  "entry_price": 2354.20,
  "reason": "Strong bullish momentum and model agreement."
}
```

---

## Pullback Entry

Usually safer than market entry.

For BUY, candidate entry levels:

```text
EMA20
EMA50
VWAP
broken resistance turned support
38.2% retracement
50% retracement
nearest support zone
```

For SELL, candidate entry levels:

```text
EMA20 from below
EMA50 from below
VWAP rejection
broken support turned resistance
nearest resistance zone
```

Example:

```json
{
  "entry_type": "LIMIT_PULLBACK",
  "entry_price": 2351.80,
  "reason": "Price is bullish but extended. Waiting for pullback to EMA20/support."
}
```

---

## Breakout Entry

For BUY:

```text
Entry above recent swing high or resistance after candle close confirmation.
```

For SELL:

```text
Entry below recent swing low or support after candle close confirmation.
```

Better rule:

```text
Do not enter immediately on the spike.
Wait for candle close above/below the level, then use retest or continuation logic.
```

---

## Stop Loss Methods

### 1. ATR-Based SL

For BUY:

```text
SL = entry_price - ATR × multiplier
```

For SELL:

```text
SL = entry_price + ATR × multiplier
```

Suggested multiplier:

```text
Normal volatility: 1.2 - 1.8 ATR
High volatility: 1.8 - 2.5 ATR
Low volatility: avoid trade or use structure SL
```

---

### 2. Structure-Based SL

For BUY:

```text
SL below recent swing low or support zone + buffer
```

For SELL:

```text
SL above recent swing high or resistance zone + buffer
```

---

### 3. Combined SL

Best approach:

```text
BUY SL = below structure, but not closer than minimum ATR distance
SELL SL = above structure, but not closer than minimum ATR distance
```

Example BUY:

```text
entry = 2354.20
ATR = 2.80
recent swing low = 2350.60
buffer = 0.50
structure SL = 2350.10
ATR SL = 2350.00
final SL = 2350.00
```

---

## Take Profit Methods

### 1. Risk/Reward TP

For BUY:

```text
TP = entry + risk × reward_ratio
```

For SELL:

```text
TP = entry - risk × reward_ratio
```

Recommended:

```text
Minimum R:R = 1.5
Preferred R:R = 2.0+
```

---

### 2. ATR-Based TP

```text
TP1 = entry ± ATR × 1.0
TP2 = entry ± ATR × 2.0
TP3 = entry ± ATR × 3.0
```

---

### 3. Structure-Based TP

For BUY:

```text
TP near next resistance
TP near previous high
TP near liquidity zone
```

For SELL:

```text
TP near next support
TP near previous low
TP near liquidity zone
```

---

## Best TP Design

Use multiple targets:

```text
TP1 = conservative target / 1R
TP2 = main target / 2R
TP3 = runner target / next major structure level
```

Example:

```json
{
  "entry": 2354.20,
  "stop_loss": 2350.00,
  "take_profit_1": 2358.40,
  "take_profit_2": 2362.60,
  "take_profit_3": 2368.00,
  "risk_reward": 2.0
}
```

---

## Entry Quality Score

Score entry quality from 0 to 100.

Good entry:

```text
Close to support for BUY
Close to resistance for SELL
Good R:R
Not chasing extended price
ATR supports target distance
Spread acceptable
Candle confirmation present
```

Bad entry:

```text
BUY directly under resistance
SELL directly above support
Price too extended from EMA20/VWAP
R:R below 1.5
SL too tight
SL too wide
```

---

## Final Trade Plan Output

```json
{
  "entry_type": "LIMIT_PULLBACK",
  "entry_price": 2351.80,
  "current_price": 2354.20,
  "stop_loss": 2348.60,
  "take_profit_1": 2355.00,
  "take_profit_2": 2358.20,
  "take_profit_3": 2364.50,
  "risk": 3.20,
  "reward": 6.40,
  "risk_reward": 2.0,
  "entry_quality_score": 82,
  "valid_for_minutes": 15,
  "reason": "Pullback entry provides better R:R than market entry."
}
```

