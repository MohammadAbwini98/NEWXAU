# 05 - Strategy Brain

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

The Strategy Brain is the main decision maker. It combines model predictions, indicators, market structure, risk context, and entry quality to produce the final recommendation.

---

## Core Rule

Even if all models say BUY or SELL, the Strategy Brain may still block the trade.

Example:

```text
Models: BUY
RSI: overbought
Price: under major resistance
Spread: high
Risk/reward: bad
Final: HOLD / BLOCKED_BY_RISK
```

---

## Strategy Brain Modules

```text
StrategyBrain
│
├── ModelConsensusService
├── IndicatorScoringService
├── TrendAnalyzer
├── MomentumAnalyzer
├── VolatilityAnalyzer
├── MarketStructureAnalyzer
├── SupportResistanceService
├── EntryQualityAnalyzer
├── SignalScoringEngine
├── SignalBlocker
├── ReasonBuilder
└── FinalRecommendationBuilder
```

---

## Scoring Design

Recommended total score: 100 points.

| Category | Max Points |
|---|---:|
| Model ensemble | 35 |
| Trend | 15 |
| Momentum | 10 |
| Volatility | 10 |
| Market structure | 15 |
| Entry quality | 10 |
| Risk quality | 5 |
| Total | 100 |

---

## Signal Status Thresholds

```text
Score >= 75 and risk passed       => RECOMMENDED
Score 60-74 and risk passed       => WEAK_RECOMMENDATION
Score < 60                        => HOLD
Any hard risk violation           => BLOCKED
High model conflict               => BLOCKED_BY_MODEL_CONFLICT
Bad R:R                           => BLOCKED_BY_LOW_RR
High-impact news active           => BLOCKED_BY_NEWS
```

---

## Model Consensus Rules

Strong BUY:

```text
Kronos = BUY
TCN = BUY
LightGBM BUY probability >= 0.60
Final model confidence >= 0.65
```

Strong SELL:

```text
Kronos = SELL
TCN = SELL
LightGBM SELL probability >= 0.60
Final model confidence >= 0.65
```

Conflict:

```text
Kronos BUY + TCN SELL
or LightGBM probability below 0.55
or no clear weighted direction
```

---

## Indicator Confirmation Rules

BUY is stronger when:

```text
price above EMA50 and EMA200
EMA20 above EMA50
RSI between 45 and 70
MACD histogram positive
ATR valid
price not too close to resistance
structure confirms higher high / higher low
```

SELL is stronger when:

```text
price below EMA50 and EMA200
EMA20 below EMA50
RSI between 30 and 55
MACD histogram negative
ATR valid
price not too close to support
structure confirms lower high / lower low
```

---

## Market Structure Rules

BUY allowed if one of these is true:

```text
Breakout above resistance confirmed by candle close
Pullback to support/EMA/VWAP confirmed by rejection
Higher low forms near support
Bullish break of structure occurs
```

SELL allowed if one of these is true:

```text
Breakdown below support confirmed by candle close
Pullback to resistance/EMA/VWAP confirmed by rejection
Lower high forms near resistance
Bearish break of structure occurs
```

---

## Hard Blockers

The Strategy Brain should block signals when:

```text
Spread is above max allowed
High-impact news window active
Risk/reward below minimum
SL distance too small
SL distance too large
Price too close to opposite support/resistance
Model conflict is high
ATR too low for expected movement
ATR extremely high without special volatility mode
Daily loss limit reached
Max consecutive losses reached
```

---

## Final Decision Flow

```text
1. Receive model predictions
2. Calculate model consensus
3. Read indicator snapshot
4. Score trend, momentum, volatility, and structure
5. Select possible signal direction
6. Ask Entry Engine for candidate entry
7. Ask SL/TP Engine for trade plan
8. Ask Risk Engine to validate the plan
9. Build final recommendation
10. Save reasons and blocked reasons
```

---

## Final Strategy Output

```json
{
  "signal": "BUY",
  "status": "RECOMMENDED",
  "score": 85,
  "confidence": 0.78,
  "strategy_bias": "BULLISH",
  "model_consensus": "STRONG_BUY",
  "indicator_bias": "BULLISH",
  "entry_quality": "GOOD",
  "risk_status": "PASSED",
  "reasons": [
    "Core models agree on BUY.",
    "Trend score is bullish.",
    "Pullback to support gives clean entry.",
    "R:R is above 2.0."
  ],
  "blocked_reasons": []
}
```

