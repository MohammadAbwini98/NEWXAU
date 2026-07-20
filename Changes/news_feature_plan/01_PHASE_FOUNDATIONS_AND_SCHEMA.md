# Phase 01 - Foundations and Database Schema

## Goal

Create the foundation for storing news items, macro events, AI analysis, strategy news state, and validation results.

This phase does not collect news yet. It prepares the backend and database so all later phases have a clean structure.

## Scope

- Add database tables.
- Add backend domain models.
- Add repository/service interfaces.
- Add configuration section for news intelligence.
- Add feature flags.
- Add initial API endpoints for reading stored news state.

## Recommended module names

```text
news_intelligence/
  collectors/
  analyzers/
  normalizers/
  repositories/
  schedulers/
  strategy_integration/
  validators/
```

Or, if your backend is currently organized by services:

```text
services/news_intelligence_service.py
services/news_ai_analyzer.py
services/economic_calendar_service.py
repositories/news_repository.py
models/news_models.py
```

## Database schema

### news_items

Stores raw collected news.

```sql
CREATE TABLE IF NOT EXISTS news_items (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(50) NOT NULL,
    source VARCHAR(100),
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    url TEXT,
    raw_text TEXT,
    raw_payload JSONB,
    news_hash VARCHAR(128) UNIQUE NOT NULL,
    relevance VARCHAR(20),
    event_type VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_items_instrument_time
ON news_items (instrument, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_items_event_type
ON news_items (event_type);
```

### macro_events

Stores known scheduled events such as CPI, FOMC, NFP, and Fed speeches.

```sql
CREATE TABLE IF NOT EXISTS macro_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    title TEXT NOT NULL,
    country VARCHAR(50),
    currency VARCHAR(20),
    scheduled_at TIMESTAMPTZ NOT NULL,
    importance VARCHAR(20) NOT NULL,
    forecast_value TEXT,
    previous_value TEXT,
    actual_value TEXT,
    source VARCHAR(100),
    url TEXT,
    raw_payload JSONB,
    event_hash VARCHAR(128) UNIQUE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_macro_events_type_time
ON macro_events (event_type, scheduled_at DESC);

CREATE INDEX IF NOT EXISTS idx_macro_events_importance_time
ON macro_events (importance, scheduled_at DESC);
```

### news_ai_analysis

Stores AI interpretation of one news item or macro event.

```sql
CREATE TABLE IF NOT EXISTS news_ai_analysis (
    id BIGSERIAL PRIMARY KEY,
    news_item_id BIGINT REFERENCES news_items(id),
    macro_event_id BIGINT REFERENCES macro_events(id),
    instrument VARCHAR(50) NOT NULL,
    event_type VARCHAR(50),
    news_relevance VARCHAR(20),
    direction VARCHAR(20),
    trade_bias VARCHAR(20),
    confidence NUMERIC(5,4),
    impact_strength VARCHAR(20),
    expected_time_window VARCHAR(50),
    market_session VARCHAR(50),
    volatility_expected VARCHAR(20),
    risk_level VARCHAR(20),
    action_level VARCHAR(30),
    should_block_trading BOOLEAN DEFAULT false,
    should_reduce_position_size BOOLEAN DEFAULT false,
    news_weight NUMERIC(5,4),
    max_position_multiplier NUMERIC(6,4),
    valid_until TIMESTAMPTZ,
    summary TEXT,
    reasoning_json JSONB,
    raw_ai_response JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (news_item_id IS NOT NULL OR macro_event_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_news_ai_analysis_instrument_time
ON news_ai_analysis (instrument, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_ai_analysis_valid_until
ON news_ai_analysis (valid_until);
```

### strategy_news_state

Stores the currently active news state that the strategy reads.

```sql
CREATE TABLE IF NOT EXISTS strategy_news_state (
    id BIGSERIAL PRIMARY KEY,
    instrument VARCHAR(50) NOT NULL UNIQUE,
    active_direction VARCHAR(20),
    active_trade_bias VARCHAR(20),
    active_confidence NUMERIC(5,4),
    active_news_weight NUMERIC(5,4),
    block_trading BOOLEAN DEFAULT false,
    reduce_position_size BOOLEAN DEFAULT false,
    action_level VARCHAR(30),
    reason TEXT,
    active_event_type VARCHAR(50),
    valid_until TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### news_impact_validation

Stores future result tracking for shadow mode.

```sql
CREATE TABLE IF NOT EXISTS news_impact_validation (
    id BIGSERIAL PRIMARY KEY,
    analysis_id BIGINT NOT NULL REFERENCES news_ai_analysis(id),
    instrument VARCHAR(50) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    horizon_minutes INT NOT NULL,
    predicted_direction VARCHAR(20),
    actual_direction VARCHAR(20),
    price_at_analysis NUMERIC(18,6),
    price_at_horizon NUMERIC(18,6),
    return_pct NUMERIC(12,6),
    was_correct BOOLEAN,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_news_impact_validation_analysis
ON news_impact_validation (analysis_id);
```

## Configuration

Add a config section like:

```yaml
news_intelligence:
  enabled: true
  shadow_mode: true
  affect_live_trading: false
  instrument: "XAUUSD"
  max_news_weight_normal: 0.20
  max_news_weight_high_impact: 0.35
  default_validity_minutes: 240
  block_before_high_impact_minutes: 15
  block_after_high_impact_minutes: 10
  min_ai_confidence_to_affect_strategy: 0.65
  min_relevance_to_analyze: "MEDIUM"
```

## Backend API endpoints

Create read-only endpoints first:

```text
GET /api/news/items?instrument=XAUUSD&limit=50
GET /api/news/analysis?instrument=XAUUSD&limit=50
GET /api/news/state?instrument=XAUUSD
GET /api/news/macro-events?from=&to=&type=
GET /api/news/validation/summary?instrument=XAUUSD
```

## Feature flags

Required flags:

```text
NEWS_COLLECTION_ENABLED=true
NEWS_AI_ANALYSIS_ENABLED=true
NEWS_STRATEGY_WEIGHT_ENABLED=false
NEWS_TRADE_BLOCK_ENABLED=false
NEWS_DASHBOARD_ENABLED=true
NEWS_SHADOW_MODE=true
```

## Acceptance criteria

- Database migration runs successfully.
- Backend can insert and read news items.
- Backend can insert and read macro events.
- Backend can insert AI analysis.
- Strategy can read `strategy_news_state` but does not use it yet.
- Dashboard/API can display empty news state without errors.
