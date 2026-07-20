# Task 11 — Production Monitoring and System Health

## Objective
Add system health monitoring so you can detect when the signal system is not safe to trust.

This task supports the whole improvement roadmap by making data, model, API, and dashboard failures visible.

## Implementation Prompt
Review the current background jobs, market data ingestion, model inference, database writes, dashboard API, and notification system. Add a SystemHealthService that reports health status and alerts when critical parts fail.

## Health Checks
Track:

```text
last candle received time
missing candle gaps
market data connection status
Capital.com/WebSocket connection status if used
model inference latency per model
model inference failures
Strategy Brain exceptions
database write failures
signal validation job status
news sync status
Telegram/notification status
dashboard API status
backtest/optimization job status
```

## Health Status
Use:

```text
HEALTHY
WARNING
CRITICAL
UNKNOWN
```

## Example Rules

```text
No new 5m candle for more than 7 minutes → WARNING
No new 5m candle for more than 12 minutes → CRITICAL
Kronos inference failed → WARNING or CRITICAL depending on fallback
Database write failed → CRITICAL
News sync failed → WARNING
All models failed → CRITICAL
```

## Integration With Recommendation Flow
Before producing a final signal:

```text
SystemHealthService.CheckTradingReadiness()
```

If critical:

```text
status = BLOCKED_BY_SYSTEM_HEALTH
reason = exact failed component
```

## Database

### `system_health_events`

```text
id
component
status
message
details_json
created_at
resolved_at
```

## API Endpoints

```text
GET /api/system/health
GET /api/system/health/events
POST /api/system/health/check-now
```

## Dashboard Changes
Add System Health card:

- Overall status
- Last candle time
- Model latency
- Failed components
- Last validation job
- Last news sync
- Last database write

## Tests
Add tests for:

- Missing candle warning
- Missing candle critical
- Model failure health event
- Critical health blocks new signal
- Healthy status allows signal

## Acceptance Criteria

- System health is visible on dashboard.
- Critical health problems block new recommendations.
- Health events are stored and searchable.
