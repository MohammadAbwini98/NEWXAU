# HOLD Signals and Live Stream Incident Report

Date: 2026-06-09
Scope: Why recent signals are all HOLD, and why websocket/live price appears closed or stale.

## Executive Summary

Two primary failures were identified:

1. Capital.com market identifier configuration is invalid for current API usage.
2. The recent signal regime is low-volatility and HOLD-favoring, amplified by baseline model behavior.

A secondary persistence issue was also found:

3. Startup/runtime state reload hits a database schema mismatch for model weight profiles.

These combine into the observed behavior:

- No fresh live ticks.
- Stale latest price.
- No fresh candles in health checks.
- Recent recommendations dominated by HOLD.

## Main Findings

### 1) Invalid Capital epic for stream and candle endpoints

Current env uses:

- CAPITALCOM_EPIC=XAUUSD

Observed runtime probe result:

- Stream subscription acknowledged, but payload returned: ERROR: XAUUSD not found.
- No quote payloads followed.
- Candle REST fetch failed with HTTP 404 on /prices/XAUUSD.

Impact:

- Live websocket tick ingestion does not receive valid quote ticks.
- Candle provider cannot refresh live candles from Capital.com for that identifier.

Code paths involved:

- src/gold_signal_system/config.py (capitalcom_epic env resolution)
- src/gold_signal_system/capital_stream.py (marketData.subscribe payload)
- src/gold_signal_system/providers.py (REST candles from /prices/{epic})

### 2) HOLD dominance in recent recommendations is real and reproducible

Database-backed analysis (latest window):

- Latest 50 signals: all HOLD.
- Volatility status in those 50: TOO_LOW for all 50.
- Blocked reason frequency: "ATR too low for expected movement." appears in all 50.
- Average reconstructed ensemble scores over latest 50:
  - buy: 0.354662
  - sell: 0.245237
  - hold: 0.400101

Why this happens in logic:

- Volatility gate marks TOO_LOW when atr_pct < 0.03.
- Strategy adds "ATR too low for expected movement." blocker.
- Baseline model artifacts include explicit HOLD support in low-vol and uncertain conditions.

Code paths involved:

- src/gold_signal_system/indicator_engine.py (TOO_LOW threshold)
- src/gold_signal_system/strategy_brain.py (ATR blocker and HOLD status behavior)
- models/_baseline_common.py (volatility_hold_boost and uncertainty_hold_boost)
- src/gold_signal_system/model_ensemble.py (weighted hold score argmax)

### 3) Startup persistence/schema mismatch on model weight profiles

Persisted health event shows startup CRITICAL with SQL error:

- column "is_active" of relation "model_weight_profiles" does not exist

Impact:

- Runtime state bootstrap can fail partially.
- Model-weight profile state may not reload/save consistently.

Code and schema involved:

- src/gold_signal_system/storage.py (PostgreSQLStorage.save_model_weight_state expects is_active)
- db/005_persistent_runtime_state.sql (adds is_active/weights_json to model_weight_profiles)
- db/schema.sql (base definition differs from code expectations)

## API-Level Confirmation During Investigation

Current running API returned:

- /api/price/latest: no live websocket tick available
- message: waiting for live stream
- /api/system/health: CRITICAL
- failed_components: No candles available.

This is consistent with the invalid epic and failed live candle refresh.

## What Is Not the Primary Cause

- ENABLE_DYNAMIC_MODEL_WEIGHTS setting is not the root cause of stream closure.
- Dynamic weights may influence directional balance, but it does not explain websocket subscription failure and /prices 404.

## Recommended Fix Order

1. Fix Capital epic mapping first.
- Replace CAPITALCOM_EPIC with the valid Capital epic identifier for Gold in your account/environment.
- Re-test both stream subscription and /prices endpoint.

2. Re-run DB migrations for runtime-state columns.
- Ensure db/005_persistent_runtime_state.sql is applied to the active schema.
- Verify model_weight_profiles has: profile_id, name, is_active, weights_json.

3. Re-evaluate HOLD saturation after feed is healthy.
- Confirm atr_pct distribution under real live candles.
- If HOLD remains too frequent, tune baseline hold behavior and/or volatility thresholds.

## Verification Checklist

- Stream subscribe returns a valid subscription key, not "ERROR: ... not found".
- /api/price/latest transitions from waiting-for-stream to LIVE updates.
- /api/system/health no longer reports "No candles available.".
- New signal window includes directional signals when market conditions permit.
- Startup no longer logs model_weight_profiles is_active column errors.
