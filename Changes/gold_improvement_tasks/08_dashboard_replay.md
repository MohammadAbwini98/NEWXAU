# Task 08 — Dashboard Transparency and Signal Replay Mode

## Objective
Improve the dashboard so it shows the full signal decision process in an organized design similar to the provided rounded-card task dashboard reference.

The dashboard must make every signal explainable.

## Implementation Prompt
Review the current frontend dashboard and backend APIs. Add a transparent Signal Details and Replay view. The UI should be professional, clean, card-based, rounded, and organized with green/gold accents inspired by the attached dashboard design.

## Design Direction
Use a layout similar to the reference image:

```text
Left sidebar
Top search/status bar
Rounded white cards
Soft background
Green primary color
Gold accent for XAUUSD
Compact analytics cards
Organized panels
Clear badges
```

Suggested colors:

```text
Background: #F7F8F5
Card: #FFFFFF
Primary Green: #0F6B3E
Deep Green: #064E2E
Gold Accent: #D4AF37
Danger Red: #D94A38
Warning Amber: #D89A2B
Text Dark: #1F2A24
Muted Text: #8A968E
Border: #E4EAE5
```

## Required Dashboard Pages

### 1. Main Dashboard
Cards:

```text
Current Signal
Confidence
Signal Grade
Risk/Reward
Market Regime
Model Agreement
Today P/L or simulated P/L
Recent Win Rate
System Health
News Risk
```

### 2. Signal Recommendation Panel
Show:

```text
BUY/SELL/HOLD
status
confidence
score
grade
entry type
entry price
SL
TP1/TP2/TP3
valid until
reason summary
```

### 3. Model Votes Panel
Show per model:

```text
model name
prediction
confidence
base weight
effective weight
recent win rate
reason for weight change
```

### 4. Indicator and Regime Panel
Show:

```text
trend state
momentum state
volatility state
support/resistance state
market regime
multi-timeframe alignment
```

### 5. Risk and Blocked Reasons Panel
Show:

```text
spread filter
news filter
session filter
R:R filter
drawdown filter
blocked reasons
```

### 6. Entry Plan Panel
Show:

```text
selected plan
rejected plans
plan scores
R:R for each plan
why selected / why rejected
```

### 7. Signal Replay View
For any past signal, show the exact snapshot:

```text
candles at signal time
model outputs
weights used
indicators
market regime
entry plans
risk filters
final score
outcome after validation
```

## Backend API Requirements
Use or add:

```text
GET /api/dashboard/summary
GET /api/dashboard/current-signal
GET /api/signals/recent
GET /api/signals/{id}
GET /api/signals/{id}/snapshot
GET /api/signals/{id}/entry-plans
GET /api/signals/{id}/replay
GET /api/models/performance/summary
GET /api/market/regime/current
GET /api/news/current-risk
```

## Replay API Shape

```json
{
  "signal": {},
  "outcome": {},
  "model_votes": [],
  "model_weights": [],
  "indicators": {},
  "market_regime": {},
  "multi_timeframe": {},
  "entry_plans": [],
  "risk_filters": [],
  "blocked_reasons": [],
  "candles_before": [],
  "candles_after": []
}
```

## UI Behavior

- Use badges for statuses.
- Use cards for each concept.
- Avoid showing raw JSON by default, but allow expanding raw snapshot.
- Use skeleton loading states.
- Use error states when API is unavailable.
- Do not show many `N/A` values. If data is missing, show a clear reason.

## Integration With Current Basecode

```text
Existing dashboard APIs
  ↓
Add new summary/replay endpoints
  ↓
Frontend services consume typed DTOs
  ↓
Reusable UI cards/components display each section
```

## Tests
Add tests for:

- Dashboard summary API returns current signal and metrics
- Replay endpoint returns full snapshot
- Missing outcome does not break dashboard
- Frontend handles blocked signal with reasons
- Frontend handles no current signal state

## Acceptance Criteria

- Dashboard shows full decision transparency.
- Any past signal can be replayed/debugged.
- UI is visually organized and close to the provided card-based design direction.
- No broken N/A-heavy layout.
