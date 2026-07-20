# Task 12 — Production Monitoring Hardening

## Goal

Add production health monitoring for data feed, models, strategy, database, dashboard, and notifications.

## Required Health Metrics

Track:

```text
last candle received time
data gaps
model inference latency
strategy decision latency
database write failures
dashboard API failures
Telegram notification failures
news provider status
backtest job status
threshold optimization job status
Capital.com connection status
```

## Health Statuses

Use:

```text
HEALTHY
WARNING
CRITICAL
```

## Health Categories

Dashboard should show:

```text
System Health
Data Feed Health
Model Health
Strategy Health
Notification Health
Database Health
News Provider Health
Backtest Job Health
```

## Logging Requirements

Add logs for:

- Every generated signal
- Every blocked signal
- Every validation outcome
- Every model weight update
- Every threshold profile change
- Every news block
- Data feed gaps
- Model inference errors
- Database write failures
- Notification failures

## Example Health Rule

```text
If no new XAUUSD 5m candle for more than 7 minutes:
Status = WARNING

If no new candle for more than 15 minutes:
Status = CRITICAL
```

## Dashboard Requirements

Show:

- Current health status
- Last successful data update
- Recent errors
- Latency metrics
- Provider statuses
- Critical warnings

## Acceptance Criteria

- Health metrics are collected.
- Dashboard shows health status.
- Critical failures are logged.
- Strategy can avoid generating signals if data is stale.
- Tests cover stale data and provider failure status.
