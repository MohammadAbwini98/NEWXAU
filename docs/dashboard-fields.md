# Dashboard Fields

Top bar:

- Instrument and timeframe
- Live XAUUSD price from Capital.com websocket ticks
- Capital.com stream status
- News status
- Manual `Run Cycle`

Main dashboard:

- Current signal, status, confidence, model consensus
- Entry, stop loss, TP1/TP2/TP3, risk/reward, risk level
- Recent outcomes with canonical lifecycle labels
- Market regime, confidence, tags, strategy mode
- Multi-timeframe alignment and conflicts
- News risk and reason

Model Ensemble:

- Latest model votes
- Model artifact status
- Dynamic base/effective weights and adjustment reasons
- Model performance metrics

Replay:

- Signal snapshot
- Outcome or pending validation message
- Regime and multi-timeframe context
- Selected and rejected entry plans
- Blocked reasons and risk filters

Health:

- Overall status: `HEALTHY`, `WARNING`, `CRITICAL`, or `UNKNOWN`
- Last candle time
- Trading allowed/blocked state
- Failed components and details

Missing values should explain the condition, for example `Pending validation`, `No high-impact event`, `Waiting for regime calculation`, or `Weights will appear after next signal cycle`.
