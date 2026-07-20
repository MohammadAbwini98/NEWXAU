# Phase 04 - AI News Impact Analyzer

## Goal

Send new XAUUSD-relevant news and macro events to an AI model and receive a strict structured JSON result describing likely XAUUSD impact.

## Important rule

The AI analyzer should not be allowed to execute trades. It only produces analysis.

## Inputs

The analyzer receives either:

1. A `news_items` record.
2. A `macro_events` record.
3. A bundle of related news items.
4. A scheduled event plus actual/forecast/previous values.

## Required AI output

The response must be strict JSON only:

```json
{
  "instrument": "XAUUSD",
  "event_type": "CPI",
  "news_relevance": "HIGH",
  "direction": "UP",
  "trade_bias": "BUY",
  "confidence": 0.72,
  "impact_strength": "MEDIUM",
  "expected_time_window": "1-4 hours",
  "market_session": "London/New York",
  "volatility_expected": "HIGH",
  "risk_level": "MEDIUM",
  "action_level": "WEIGHT_ONLY",
  "should_block_trading": false,
  "should_reduce_position_size": false,
  "summary": "Short explanation.",
  "reasoning_points": [
    "Point 1",
    "Point 2",
    "Point 3"
  ],
  "recommended_strategy_action": {
    "news_weight": 0.25,
    "max_position_multiplier": 1.10,
    "valid_until_minutes": 240
  }
}
```

## Allowed values

### news_relevance

```text
LOW
MEDIUM
HIGH
CRITICAL
```

### direction

```text
UP
DOWN
NEUTRAL
MIXED
UNKNOWN
```

### trade_bias

```text
BUY
SELL
HOLD
NO_TRADE
```

### impact_strength

```text
LOW
MEDIUM
HIGH
EXTREME
```

### volatility_expected

```text
LOW
MEDIUM
HIGH
EXTREME
```

### risk_level

```text
LOW
MEDIUM
HIGH
EXTREME
```

### action_level

```text
INFO_ONLY
WEIGHT_ONLY
RISK_REDUCE
BLOCK_NEW_TRADES
MANUAL_REVIEW
```

## Prompt template

Use this prompt for each item:

```text
You are an XAUUSD market-news impact analyst for a trading decision-support system.

Analyze the following news or macro event only for its likely impact on XAUUSD / Gold.

Do not provide financial advice. Do not claim certainty. Return strict JSON only.

Instrument: XAUUSD
Current context:
- Timeframe used by system: 5-minute candles
- System uses KRONOS model + technical strategy + risk engine
- Your output will be used as a news/risk weight, not as a direct trade command

News/event:
Title: {title}
Source: {source}
Published/Scheduled time: {time}
Event type: {event_type}
Forecast: {forecast_value}
Previous: {previous_value}
Actual: {actual_value}
Raw text: {raw_text}

Consider:
- USD impact
- US Treasury yield impact
- Fed rate expectation impact
- safe-haven demand
- inflation expectation
- geopolitical risk
- expected market session
- likely volatility window

Return JSON using exactly this schema:
{schema_here}
```

## Macro-event-specific logic

### CPI event prompt additions

```text
For CPI:
- Compare actual vs forecast if available.
- Higher-than-expected CPI can be gold-negative if it increases USD/yields/rate expectations.
- Lower-than-expected CPI can be gold-positive if it lowers USD/yields/rate expectations.
- If market reaction is ambiguous, choose MIXED or NEUTRAL and increase volatility/risk.
```

### FOMC event prompt additions

```text
For FOMC:
- Classify tone as hawkish, dovish, neutral, or mixed.
- Hawkish is usually XAUUSD-negative.
- Dovish is usually XAUUSD-positive.
- Press conferences can reverse the first reaction.
```

### NFP event prompt additions

```text
For NFP:
- Compare jobs, unemployment rate, and wage growth if available.
- Strong jobs/wage data can be XAUUSD-negative through USD/yields.
- Weak jobs/wage data can be XAUUSD-positive through lower-rate expectations.
```

### Fed speech prompt additions

```text
For Fed speeches:
- Classify the tone as hawkish, dovish, neutral, or mixed.
- Focus on rate path, inflation, employment, balance sheet, and risk language.
```

### War escalation prompt additions

```text
For war escalation:
- Determine whether the news increases or reduces geopolitical risk.
- Escalation can be XAUUSD-positive through safe-haven demand.
- If USD strength is also likely, mark as MIXED and high volatility.
```

## Validation of AI output

Before saving:

1. Parse JSON.
2. Validate required fields.
3. Validate allowed enum values.
4. Clamp confidence to 0.00-1.00.
5. Clamp news weight to configured maximum.
6. Reject or retry if invalid.

## Confidence rules

Recommended mapping:

```text
0.00-0.49 = weak / info only
0.50-0.64 = monitor only
0.65-0.79 = can affect strategy weight
0.80-0.89 = can reduce risk or block if high impact
0.90-1.00 = require caution; do not blindly trust extreme confidence
```

## News weight rules

```text
LOW relevance:      max weight 0.00
MEDIUM relevance:   max weight 0.10
HIGH relevance:     max weight 0.20
CRITICAL relevance: max weight 0.35
```

## Storage behavior

For every valid AI result:

1. Save to `news_ai_analysis`.
2. Set `valid_until` using `valid_until_minutes`.
3. Update dashboard feed.
4. Trigger news-state aggregator.

## Error handling

If AI fails:

```text
- Mark item as analysis_failed.
- Retry with exponential backoff.
- Do not block trading because of AI failure.
- Dashboard should show analyzer degraded if repeated failures happen.
```

## Acceptance criteria

- New relevant news is analyzed once.
- AI response is stored as valid JSON.
- Invalid AI JSON is rejected or retried.
- Analysis includes event type, direction, confidence, risk, action level, and validity window.
- No trading decision is made directly by the analyzer.
