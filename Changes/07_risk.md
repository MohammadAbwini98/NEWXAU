# 07 - Risk Engine

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

Protect the system from unsafe trades even when models and indicators look good.

The Risk Engine has permission to block any signal.

---

## Risk Rules

| Rule | Suggested Default |
|---|---:|
| Minimum R:R | 1.5 |
| Preferred R:R | 2.0 |
| Max risk per trade | 0.5% - 1.0% |
| Max daily loss | 2% - 3% |
| Max consecutive losses | 3 |
| Max open trades | 1 - 3 |
| Max spread | Broker-specific |
| News block before event | 15 - 30 minutes |
| News block after event | 15 - 30 minutes |
| Signal expiry | 1 - 3 candles |

---

## Hard Blockers

Block signal when:

```text
spread > max_allowed_spread
risk_reward < minimum_rr
high_impact_news_window = true
daily_loss_limit_reached = true
consecutive_loss_limit_reached = true
sl_distance_too_small = true
sl_distance_too_large = true
price_too_close_to_opposite_level = true
model_conflict_high = true
atr_too_low = true
```

---

## Spread Filter

Gold spreads can expand quickly.

Rules:

```text
If spread is normal: allow.
If spread is elevated: reduce confidence.
If spread is high: block signal.
```

Output:

```json
{
  "spread_status": "ACCEPTABLE",
  "spread": 0.25,
  "max_allowed_spread": 0.40
}
```

---

## News Filter

High-impact news should block or reduce confidence.

Rules:

```text
High-impact event within next 30 minutes => BLOCKED_BY_NEWS
High-impact event occurred within last 15 minutes => BLOCKED_BY_NEWS or reduce confidence
Medium-impact event => reduce confidence
No event => clear
```

---

## Volatility Filter

Use ATR and realized volatility.

Rules:

```text
ATR too low => not enough movement, block
ATR normal => allow
ATR very high => reduce position size
ATR extreme => block unless special volatility mode is enabled
```

---

## Position Sizing

Basic formula:

```text
position_size = account_risk_amount / stop_loss_distance_value
```

Example:

```text
Account = 10,000
Risk = 1% = 100
SL distance = 5.0 dollars
Position size must be calculated based on broker contract rules.
```

The system must never place position sizing blindly without broker-specific pip/tick value rules.

---

## Risk Output

```json
{
  "risk_status": "PASSED",
  "risk_reward": 2.0,
  "spread_status": "ACCEPTABLE",
  "news_status": "CLEAR",
  "volatility_status": "VALID",
  "position_size_status": "VALID",
  "blocked_reasons": []
}
```

Blocked example:

```json
{
  "risk_status": "BLOCKED",
  "blocked_reasons": [
    "Risk/reward is below 1.5",
    "Price is too close to resistance for BUY"
  ]
}
```

---

## Risk Dashboard Metrics

Show these on the dashboard:

- Today P/L
- Daily loss limit usage
- Consecutive losses
- Active open recommendations
- Average R:R
- Win rate
- Profit factor
- Current spread
- Current ATR state
- News status
- Risk engine status

