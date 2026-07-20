# Task 07 — Gold Economic News Filter

## Objective
Add a high-impact news filter for Gold/XAUUSD. Gold reacts strongly to USD economic events, Federal Reserve events, inflation data, employment data, and geopolitical risk.

## Implementation Prompt
Review the current risk filters and scheduled jobs. Add an EconomicNewsFilter that can block, reduce confidence, or switch strategy mode around high-impact news events. The filter must be visible in the signal snapshot and dashboard.

## Important Events for Gold
Track at least:

```text
FOMC statement
Federal funds rate decision
Fed chair speech
CPI
Core CPI
PPI
Core PPI
NFP / Nonfarm Payrolls
Unemployment rate
Average hourly earnings
GDP
ISM PMI
Retail sales
Initial jobless claims
US dollar high-impact events
major geopolitical alerts if available
```

## News Event Entity

### `economic_news_events`

Fields:

```text
id
source
event_name
country
currency
impact: LOW/MEDIUM/HIGH
scheduled_at
actual
forecast
previous
status: SCHEDULED/RELEASED/CANCELLED
created_at
updated_at
```

## Filter Output

```json
{
  "status": "BLOCKED",
  "reason": "High-impact USD CPI event in 18 minutes",
  "event_name": "US CPI YoY",
  "minutes_to_event": 18,
  "cooldown_minutes_after": 30,
  "confidence_multiplier": 0.0
}
```

## Filter Rules

### Default Rules

```text
Block new trades 30 minutes before HIGH impact USD news.
Block new trades 15 minutes after HIGH impact USD news.
Reduce confidence 15-30 minutes after event if volatility is still high.
Allow existing trade management separately from new entries.
```

### Optional Rules

```text
Medium impact event: reduce confidence by 10%-20%.
High volatility after event: keep blocked until ATR normalizes.
News spike detected: mark regime as NEWS_SPIKE.
```

## Integration With Current Basecode

```text
NewsSyncJob updates events
  ↓
EconomicNewsFilter checks upcoming/recent news
  ↓
MarketRegimeDetector can mark NEWS_SPIKE
  ↓
RiskEngine blocks or penalizes signal
  ↓
FinalRecommendationBuilder records blocked reason
```

## Data Source
Implement using the currently available news/calendar source in the project. If no source exists yet, create an abstraction:

```csharp
public interface IEconomicCalendarProvider
{
    Task<IReadOnlyList<EconomicNewsEvent>> GetEventsAsync(DateTime from, DateTime to, CancellationToken cancellationToken);
}
```

Provide a mock/manual provider first if external integration is not ready.

## API Endpoints

```text
GET /api/news/upcoming
GET /api/news/current-risk
POST /api/news/sync
```

## Dashboard Changes
Add News Risk card:

- Upcoming high-impact event
- Time remaining
- Current status: Safe / Caution / Blocked
- Reason
- Cooldown time

## Tests
Add tests for:

- Signal blocked 30 minutes before high-impact USD news
- Signal blocked 15 minutes after release
- Medium-impact event reduces confidence but does not block
- No event means safe
- News status included in blocked reasons

## Acceptance Criteria

- Risk Engine checks news before final recommendation.
- Blocked signal shows exact news reason.
- Dashboard shows upcoming high-impact news risk.
