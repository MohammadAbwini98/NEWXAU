# Database Schema

Schema source:

- `db/schema.sql`

Migrations:

- `db/001_signal_lifecycle.sql`
- `db/002_improvement_roadmap.sql`
- `db/003_production_hardening.sql`

Main tables:

- `market_candles`
- `indicator_snapshots`
- `model_predictions`
- `ensemble_predictions`
- `strategy_decisions`
- `trade_recommendations`
- `signal_snapshots`
- `signal_outcomes`
- `model_signal_predictions`
- `model_prediction_outcomes`
- `signal_entry_plans`
- `signal_timeframe_confirmations`
- `signal_market_regimes`
- `risk_checks`
- `model_performance`
- `model_weight_profiles`
- `model_dynamic_weights`
- `economic_news_events`
- `backtest_runs`
- `backtest_windows`
- `backtest_signals`
- `strategy_parameter_profiles`
- `optimization_runs`
- `optimization_candidates`
- `threshold_profiles`
- `threshold_optimization_runs`
- `threshold_optimization_results`
- `model_weight_profile_versions`
- `system_health_events`
- `system_settings`

Signal traceability:

1. `trade_recommendations` stores the final recommendation.
2. `signal_snapshots` stores model votes, weights, indicators, risk filters, regime, timeframes, entry plans, and raw recommendation JSON.
3. `signal_outcomes` stores validation result and PnL details.
4. `model_signal_predictions` links each model vote to the signal.
5. `model_prediction_outcomes` links each model prediction to the validated signal result.
