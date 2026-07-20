# 03 - Model Ensemble Design

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

Use multiple models as prediction advisors, not as direct trade executors.

The ensemble should produce normalized predictions that the Strategy Brain can evaluate with indicators and risk rules.

---

## Core Models

| Model | Role | Priority |
|---|---|---:|
| Kronos fine-tuned | Main high-capacity market context model | 1 |
| LightGBM / XGBoost | Explainable feature-based confirmation model | 1 |
| TCN | Main smaller deep sequence model | 1 |
| CNN + LSTM | Candle pattern + sequence confirmation | 2 |
| PatchTST | Advanced time-series sequence model | 2 |
| N-HiTS / N-BEATS | Forecast future return/range | 2 |
| GRU | Fast sequence baseline | 3 |
| LSTM | Secondary sequence baseline | 3 |
| Small Transformer | Long-context experimental model | 3 |
| 1D CNN | Short-term candle pattern detector | 3 |

---

## Recommended Production Start

Start with:

```text
Kronos + LightGBM + TCN
```

Then add:

```text
CNN+LSTM + PatchTST + N-HiTS
```

Keep the rest experimental until backtesting proves that they improve results.

---

## Model Output Contract

Every model must return the same normalized structure:

```json
{
  "model_name": "TCN",
  "timeframe": "5m",
  "signal": "BUY",
  "buy_probability": 0.68,
  "sell_probability": 0.12,
  "hold_probability": 0.20,
  "confidence": 0.68,
  "expected_return": 0.0018,
  "expected_range": 4.2,
  "prediction_horizon_candles": 6,
  "model_version": "tcn_xauusd_5m_v1",
  "created_at": "2026-06-07T20:00:00Z"
}
```

---

## Suggested Ensemble Weights

Initial weights:

```json
{
  "kronos": 0.30,
  "tcn": 0.25,
  "lightgbm": 0.20,
  "patchtst": 0.10,
  "cnn_lstm": 0.10,
  "nhits": 0.05
}
```

Experimental weights can be added later only after validation.

---

## Weighted Voting Logic

```text
BUY score  = sum(model_weight × model_buy_probability)
SELL score = sum(model_weight × model_sell_probability)
HOLD score = sum(model_weight × model_hold_probability)
```

The highest score becomes the ensemble direction.

Example:

```json
{
  "buy_score": 0.71,
  "sell_score": 0.12,
  "hold_score": 0.17,
  "ensemble_signal": "BUY",
  "ensemble_confidence": 0.71
}
```

---

## Agreement Factor

The Strategy Brain should reward model agreement and penalize conflict.

```text
Strong agreement: 1.10
Normal agreement: 1.00
Mixed agreement: 0.85
High conflict: 0.65
```

Example:

```text
Kronos BUY, TCN BUY, LightGBM BUY = strong agreement
Kronos BUY, TCN SELL, LightGBM HOLD = high conflict
```

---

## Model Quality Tracking

Track each model continuously:

- BUY precision
- SELL precision
- HOLD accuracy
- Win rate when model agrees with final signal
- Profit factor contribution
- False signal rate
- Average return after signal
- Model drift

Models with poor live or paper performance should be automatically down-weighted.

---

## Model Selection Rule

Do not keep a model because it sounds advanced. Keep it only if it improves:

```text
profit factor
max drawdown
BUY precision
SELL precision
average R:R
number of quality trades
```

---

## Final Ensemble Output

```json
{
  "ensemble_signal": "BUY",
  "ensemble_confidence": 0.71,
  "buy_score": 0.71,
  "sell_score": 0.12,
  "hold_score": 0.17,
  "agreement": "STRONG",
  "active_models": ["kronos", "tcn", "lightgbm"],
  "conflicting_models": ["patchtst"],
  "summary": "Core models are bullish with acceptable agreement."
}
```

