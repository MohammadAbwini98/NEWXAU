# 08 - Web Dashboard UI Design

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

Create a professional web dashboard for the Gold signal recommendation system.

The design should be inspired by the attached dashboard image:

- White/soft background
- Dark green primary color
- Rounded cards
- Clean sidebar
- Minimal shadows
- Large KPI cards
- Organized panels
- Clear typography
- Calm professional trading interface

Do not copy the task-management content. Use the same clean visual style for trading and signal analysis.

---

## Visual Style

### Colors

```text
Primary green: #0F5C38
Dark green: #063D28
Light green: #E8F5EE
Background: #F7F8F7
Card background: #FFFFFF
Muted text: #8A9490
Danger red: #D94A4A
Warning amber: #E6A23C
Neutral gray: #E9ECEA
Border: #E3E8E5
```

### UI Shape

```text
Border radius: 18px - 24px
Card padding: 20px - 28px
Sidebar width: 240px
Main content max width: fluid
Shadow: soft and minimal
```

### Typography

```text
Dashboard title: 28px - 34px
Section title: 16px - 18px
KPI number: 32px - 44px
Small labels: 12px - 14px
```

---

## Main Layout

```text
┌──────────────────────────────────────────────────────────────┐
│ App Shell                                                     │
│                                                              │
│ ┌──────────────┐ ┌─────────────────────────────────────────┐ │
│ │ Sidebar      │ │ Top Bar                                 │ │
│ │              │ ├─────────────────────────────────────────┤ │
│ │ Dashboard    │ │ KPI Cards                               │ │
│ │ Signals      │ │ Recommendation Panel                    │ │
│ │ Models       │ │ Model Votes + Indicators + Risk         │ │
│ │ Indicators   │ │ Entry / SL / TP + Chart + History       │ │
│ │ Backtesting  │ │                                         │ │
│ │ Settings     │ │                                         │ │
│ └──────────────┘ └─────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Sidebar Navigation

Items:

```text
Dashboard
Live Signals
Signal History
Model Ensemble
Indicators
Risk Center
Backtesting
Paper Trading
Settings
Logs
```

Sidebar should use icons and active green highlight similar to the attached design.

---

## Top Bar

Content:

- Search signal/history
- Current instrument: XAUUSD
- Current timeframe selector: 1m / 5m / 15m / 1h
- Market status
- News status
- Notifications icon
- User/settings menu

---

## Dashboard KPI Cards

Use four large cards at the top, similar to the screenshot.

Recommended cards:

### Card 1 - Current Signal

```text
BUY / SELL / HOLD
Confidence
Status
```

### Card 2 - Model Consensus

```text
Strong Buy / Mixed / Strong Sell
Active models
Agreement percentage
```

### Card 3 - Risk Quality

```text
Passed / Blocked
R:R
Spread status
```

### Card 4 - Today's Performance

```text
Win rate
Profit factor
P/L
Number of signals
```

---

## Main Recommendation Panel

This should be the most important card.

Show:

```text
Signal: BUY
Status: RECOMMENDED
Confidence: 78%
Score: 85/100
Entry type: LIMIT_PULLBACK
Entry price: 2351.80
Current price: 2354.20
SL: 2348.60
TP1: 2355.00
TP2: 2358.20
TP3: 2364.50
Risk/Reward: 2.0
Valid for: 15 minutes
```

Use color status:

```text
BUY = green
SELL = red
HOLD = gray
BLOCKED = amber/red
```

---

## Model Votes Panel

Show each model in a compact row/card:

| Model | Signal | Confidence | Weight | Status |
|---|---|---:|---:|---|
| Kronos | BUY | 71% | 30% | Confirmed |
| TCN | BUY | 68% | 25% | Confirmed |
| LightGBM | BUY | 64% | 20% | Confirmed |
| PatchTST | HOLD | 52% | 10% | Weak |
| N-HiTS | +0.18% | 58% | 5% | Forecast Support |

Visual idea:

```text
Small green badges for BUY
Small red badges for SELL
Small gray badges for HOLD
```

---

## Indicator Summary Panel

Use grouped cards:

```text
Trend: Bullish, 82/100
Momentum: Positive, 74/100
Volatility: Valid, ATR 2.8
Structure: Pullback to Support
Session: New York
News: Clear
```

Add mini progress bars like the project-progress section in the attached dashboard.

---

## Entry / SL / TP Card

Design like a trading plan card:

```text
Entry       2351.80
Stop Loss   2348.60
TP1         2355.00
TP2         2358.20
TP3         2364.50
R:R         2.0
```

Also show:

```text
Entry quality score
SL method: ATR + Structure
TP method: R:R + Resistance
```

---

## Risk Center Card

Show:

```text
Spread: Acceptable
News: Clear
ATR: Valid
Daily Loss: 0.4% / 3.0%
Consecutive Losses: 1 / 3
Max Open Trades: 1 / 3
Risk Status: PASSED
```

Blocked signal example:

```text
Risk Status: BLOCKED
Reason: Price too close to resistance. R:R below 1.5.
```

---

## Chart Section

Show a candlestick chart with overlays:

- Entry line
- Stop loss line
- TP1/TP2/TP3 lines
- EMA20/EMA50/EMA200
- Support/resistance zones
- Signal marker
- Validity window

Optional libraries:

```text
TradingView Lightweight Charts
ApexCharts
ECharts
```

---

## Signal History Table

Columns:

```text
Time
Instrument
Timeframe
Signal
Status
Confidence
Entry
SL
TP
R:R
Outcome
Profit/Loss
Reason
```

Filters:

```text
Recommended
Blocked
BUY
SELL
HOLD
Today
This week
By model agreement
By outcome
```

---

## Signal Details Modal

When the user clicks a signal, show full explanation:

- Model votes
- Indicator snapshot
- Entry calculation
- SL calculation
- TP calculation
- Risk checks
- Reasons
- Blocked reasons
- Outcome tracking
- Raw JSON

---

## Dashboard Pages

### 1. Dashboard
Overview cards + live recommendation.

### 2. Live Signals
Current signal cycle and live updates.

### 3. Signal History
Searchable table of all generated signals.

### 4. Model Ensemble
Model predictions, weights, confidence, performance.

### 5. Indicators
Current indicator values and historical indicator states.

### 6. Risk Center
Risk filters, limits, spread, news, drawdown.

### 7. Backtesting
Backtest reports and model comparison.

### 8. Paper Trading
Live validation without real execution.

### 9. Settings
Thresholds, weights, risk limits, active models.

---

## Dashboard API Endpoints

Suggested endpoints:

```text
GET /api/dashboard/summary
GET /api/signals/latest
GET /api/signals/history
GET /api/signals/{id}
GET /api/models/latest-votes
GET /api/indicators/latest
GET /api/risk/status
GET /api/backtest/summary
POST /api/settings/model-weights
POST /api/settings/risk-limits
```

---

## Realtime Updates

Use SignalR or WebSocket.

Events:

```text
signal.created
signal.updated
risk.blocked
model.predicted
indicator.updated
trade.outcome.updated
```

---

## UI Implementation Notes

Recommended stack:

```text
Frontend: Angular or React
Backend: ASP.NET Core Web API
Realtime: SignalR
Charts: TradingView Lightweight Charts
Database: PostgreSQL
```

Card design should remain clean, with enough spacing and no clutter. The dashboard must explain the recommendation, not only display numbers.

