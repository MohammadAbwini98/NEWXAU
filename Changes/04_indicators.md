# 04 - Indicator Engine

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

Build a massive but organized indicator engine that supports the Strategy Brain.

Indicators must be grouped by purpose. The system should not randomly mix all indicators. Each indicator group should produce a score and bias.

---

## Indicator Groups

```text
Trend Indicators
Momentum Indicators
Volatility Indicators
Market Structure Indicators
Support/Resistance Indicators
Volume/Activity Indicators
Session/Time Filters
News/Event Filters
Candle Pattern Indicators
Risk Context Indicators
```

---

## 1. Trend Indicators

Used to identify market direction.

Recommended indicators:

- EMA 20
- EMA 50
- EMA 100
- EMA 200
- SMA 50
- SMA 200
- ADX
- Supertrend
- Ichimoku Cloud
- VWAP

Example BUY bias:

```text
price > EMA20
EMA20 > EMA50
EMA50 > EMA200
ADX > 20
price above VWAP
```

Trend output:

```json
{
  "trend_bias": "BULLISH",
  "trend_score": 82,
  "reasons": [
    "Price above EMA50 and EMA200",
    "EMA20 is above EMA50",
    "ADX confirms trend strength"
  ]
}
```

---

## 2. Momentum Indicators

Used to confirm strength and avoid exhausted trades.

Recommended indicators:

- RSI
- Stochastic RSI
- MACD
- CCI
- ROC
- Williams %R
- Momentum oscillator

Example BUY confirmation:

```text
RSI between 45 and 70
MACD histogram positive
ROC positive
Stochastic RSI recovering from oversold
```

Avoid:

```text
BUY directly into extreme overbought resistance
SELL directly into extreme oversold support
```

---

## 3. Volatility Indicators

Very important for Gold/XAUUSD.

Recommended indicators:

- ATR 14
- ATR percentage
- Bollinger Bands
- Keltner Channels
- Donchian Channel
- Historical volatility
- Realized volatility
- Average candle range

Use volatility for:

- Stop loss distance
- Take profit distance
- Trade blocking
- Position sizing
- Breakout detection

Example volatility decision:

```text
ATR too low  => block because movement is weak
ATR normal   => allow normal risk
ATR too high => reduce position size or widen SL
```

---

## 4. Market Structure Indicators

This is one of the most important groups.

Recommended structure features:

- Swing high
- Swing low
- Higher high
- Higher low
- Lower high
- Lower low
- Break of structure
- Change of character
- Liquidity zones
- Supply/demand zones
- Order blocks
- Fair value gaps
- Previous day high/low
- Previous week high/low
- Session high/low

Example:

```text
BUY is stronger if price breaks above resistance and retests it as support.
SELL is stronger if price breaks below support and retests it as resistance.
```

---

## 5. Support / Resistance Engine

Sources:

- Recent swing highs/lows
- Pivot points
- Previous day high/low
- Previous week high/low
- Session high/low
- Volume/tick-volume zones
- Psychological price levels
- Repeated rejection zones

Output:

```json
{
  "nearest_support": 2348.60,
  "nearest_resistance": 2362.50,
  "distance_to_support": 5.60,
  "distance_to_resistance": 8.30,
  "structure_bias": "BULLISH_PULLBACK"
}
```

---

## 6. Volume / Activity Indicators

For Gold CFD or broker data, volume may be tick volume. Use it as confirmation only.

Recommended:

- Tick volume
- Volume moving average
- Volume spike
- OBV
- VWAP
- Relative volume

Example:

```text
Breakout with above-average volume is stronger than breakout with weak volume.
```

---

## 7. Session / Time Filters

Gold behavior changes by session.

Track:

- Asian session
- London session
- New York session
- London/New York overlap
- Rollover time
- Friday late session
- Market open/close

Rules:

```text
Prefer London and New York sessions.
Reduce confidence in dead Asian range unless a special range strategy is active.
Avoid new trades near market close or rollover.
```

---

## 8. News / Event Filters

Critical for Gold.

High-impact events:

- FOMC
- CPI
- PPI
- NFP
- Unemployment rate
- Federal Reserve speeches
- Interest rate decisions
- US dollar news
- Geopolitical events

Rules:

```text
Block new signals 15-30 minutes before high-impact news.
Block or reduce confidence 15-30 minutes after high-impact news.
Allow special news mode only if explicitly implemented and backtested.
```

---

## 9. Candle Pattern Indicators

Useful for entry confirmation.

Recommended:

- Engulfing candle
- Pin bar / rejection wick
- Inside bar
- Breakout candle
- Doji near key level
- Strong body candle
- Wick ratio
- Candle body percentage

Example:

```text
BUY pullback entry is stronger if bullish rejection candle appears at EMA20/support.
```

---

## Indicator Snapshot Output

Every signal cycle should save one snapshot:

```json
{
  "timeframe": "5m",
  "trend": {
    "bias": "BULLISH",
    "score": 82
  },
  "momentum": {
    "bias": "POSITIVE",
    "score": 74
  },
  "volatility": {
    "status": "VALID",
    "atr": 2.8
  },
  "structure": {
    "bias": "PULLBACK_TO_SUPPORT",
    "nearest_support": 2348.6,
    "nearest_resistance": 2362.5
  },
  "session": "NEW_YORK",
  "news_filter": "CLEAR"
}
```

