# Phase 03 - Economic Calendar and Macro Events

## Goal

Track scheduled and unscheduled high-impact events that commonly move XAUUSD:

- CPI
- FOMC
- NFP
- Major Fed speeches
- War escalation / geopolitical shocks

These events should create risk windows before and after release times.

## Why this matters for XAUUSD

Gold is heavily affected by:

```text
US inflation expectations
US interest-rate expectations
US dollar strength
US Treasury yields
safe-haven demand
geopolitical risk
```

CPI, FOMC, NFP, and Fed speeches can quickly change USD/yield expectations. War escalation can quickly increase safe-haven demand.

## Event types

Use controlled enum-like values:

```text
CPI
FOMC_RATE_DECISION
FOMC_MINUTES
NFP
FED_SPEECH
WAR_ESCALATION
GEOPOLITICAL_RISK
PPI
JOBLESS_CLAIMS
RETAIL_SALES
ISM_PMI
GENERAL_GOLD_NEWS
```

## Scheduled event behavior

### CPI

Typical interpretation:

```text
Higher CPI than expected:
  USD/yields may rise.
  Gold can fall due to higher-rate expectations.
  But inflation-hedge behavior can sometimes support gold.

Lower CPI than expected:
  Rate-cut expectations may rise.
  USD/yields may fall.
  Gold can rise.
```

### FOMC

Typical interpretation:

```text
Hawkish Fed:
  Higher rates for longer.
  USD/yields up.
  Gold pressure down.

Dovish Fed:
  Lower-rate expectations.
  USD/yields down.
  Gold support up.
```

### NFP

Typical interpretation:

```text
Strong jobs report:
  Economy strong.
  Fed may delay cuts.
  USD/yields may rise.
  Gold pressure down.

Weak jobs report:
  Economy slowing.
  Rate-cut expectations rise.
  USD/yields may fall.
  Gold support up.
```

### Major Fed speeches

Typical interpretation:

```text
Hawkish speech:
  Gold risk down.

Dovish speech:
  Gold risk up.

Unclear speech:
  Volatility risk high.
```

### War escalation

Typical interpretation:

```text
Escalation:
  Safe-haven demand may increase.
  Gold often rises.

De-escalation:
  Safe-haven premium may fade.
  Gold can fall or consolidate.
```

## Economic calendar collector

Create a collector that can import events from:

```text
Free/public economic calendar sources
Manual CSV upload
Manual dashboard entry
Optional paid data source later
```

For the first release, manual upload or dashboard entry is acceptable if a stable free API is not available.

## Macro event fields

Required fields:

```json
{
  "event_type": "CPI",
  "title": "US CPI YoY",
  "country": "US",
  "currency": "USD",
  "scheduled_at": "2026-07-15T12:30:00Z",
  "importance": "HIGH",
  "forecast_value": "3.1%",
  "previous_value": "3.0%",
  "actual_value": null,
  "source": "manual_calendar",
  "status": "SCHEDULED"
}
```

## Risk windows

Create risk windows around high-impact events.

Recommended defaults:

| Event | Before release | After release | Default action |
|---|---:|---:|---|
| CPI | 30 min | 15 min | Block new trades |
| FOMC rate decision | 60 min | 30 min | Block new trades |
| FOMC press conference | 30 min | 30 min | Block new trades |
| NFP | 30 min | 15 min | Block new trades |
| Major Fed speech | 15 min | 15 min | Reduce size or block |
| War escalation | immediate | 2-6 hours | Manual review or reduce risk |

## Strategy behavior before scheduled high-impact events

```text
If high-impact event is within risk window:
  - Do not open new trades.
  - Manage existing trades normally.
  - Optionally tighten stop-loss or reduce exposure.
  - Dashboard shows event countdown.
```

## Strategy behavior after event release

```text
1. Wait for first 5m candle close.
2. Collect actual vs forecast if available.
3. Analyze initial market reaction.
4. Check DXY/yields if available later.
5. Allow trading only after volatility stabilizes or strategy confirms direction.
```

## War escalation detector

War/geopolitical escalation is not scheduled. Detect it from news titles/body using keywords:

```text
missile attack
military strike
invasion
retaliation
escalation
ceasefire collapse
oil supply disruption
regional conflict
NATO emergency
UN Security Council emergency
sanctions escalation
```

Severity rules:

| Severity | Example | Action |
|---|---|---|
| LOW | Political statement | Info only |
| MEDIUM | New threat or limited incident | Reduce size |
| HIGH | Actual strike, major escalation | Block or manual review |
| EXTREME | Regional war expansion | Manual review, disable auto entries |

## Backend jobs

Create scheduled jobs:

```text
macro_event_import_job      every 6 hours
macro_event_refresh_job     every 30 minutes on event days
macro_risk_window_job       every 1 minute
war_escalation_scan_job     every 2-5 minutes
```

## API endpoints

```text
GET  /api/news/macro-events?from=&to=&type=
POST /api/news/macro-events/manual
PUT  /api/news/macro-events/{id}/actual
GET  /api/news/risk-window?instrument=XAUUSD
```

## Acceptance criteria

- CPI, FOMC, NFP, Fed speech, and war-escalation events can be stored.
- Dashboard/API can show upcoming high-impact events.
- Risk windows are calculated correctly.
- Strategy can read whether a block/reduce-risk window is active.
- No live trade is blocked yet unless feature flag enables it.
