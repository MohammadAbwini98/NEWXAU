# Task 11 — Dashboard Production Upgrade

## Goal

Upgrade the dashboard so it clearly explains every signal decision and exposes production-hardening details.

The design should be clean, professional, and similar in style to the provided rounded-card dashboard screenshot.

## Required Pages or Panels

Add or improve:

```text
1. Live Recommendation
2. Entry / SL / TP Plans
3. Model Votes
4. Dynamic Model Weights
5. Indicator Summary
6. Market Regime
7. Multi-Timeframe Matrix
8. Risk Filters
9. News Filter
10. Blocked Reasons
11. Signal Replay
12. Signal Validation
13. Walk-Forward Backtest
14. Threshold Optimization
15. Production Health
```

## Design Style

Use:

- Clean left sidebar
- Rounded cards
- Green/gold professional theme
- Organized cards
- Summary-first layout
- Drill-down for details
- No clutter

Suggested theme:

```text
Background: #F7F8F5
Card: #FFFFFF
Primary green: #0F6B3E
Gold accent: #D4AF37
Danger red: #D94A38
Text dark: #1F2A24
Muted text: #8A968E
```

## No N/A Rule

No `N/A` values should appear unless truly unavailable.

If a value is unavailable, show a clear reason:

```text
Unavailable because no validated signals exist yet.
Waiting for next candle.
No active threshold profile configured.
News provider is disabled in current environment.
```

## Live Recommendation Requirements

Show:

- Current signal
- Status
- Confidence
- Score
- Grade
- Entry
- SL
- TP1/TP2/TP3
- Risk/reward
- Valid until
- Main reasons
- Blocked reasons if any

## Replay Mode Requirements

For any past signal, show:

- Candles at signal time
- Model outputs
- Indicator snapshot
- Market regime
- Multi-timeframe matrix
- Entry plan candidates
- Selected/rejected plans
- Risk filters
- Final decision
- Validation outcome

## Acceptance Criteria

- Dashboard shows all important production modules.
- No unexplained N/A values.
- Signal decisions are explainable.
- User can inspect why signal was recommended or blocked.
- UI follows clean rounded-card design.
