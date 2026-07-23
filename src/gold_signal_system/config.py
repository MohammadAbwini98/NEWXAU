from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

from .desktop_runtime import resolve_resource_path, resolve_runtime_path


CAPITAL_DEMO_BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
CAPITAL_LIVE_BASE_URL = "https://api-capital.backend-capital.com/api/v1"


def _load_env_file(path: Path, allowed_prefixes: tuple[str, ...] | None = None) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if allowed_prefixes is not None and not key.startswith(allowed_prefixes):
            continue
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_runtime_env_files() -> None:
    local_env = Path.cwd() / ".env"
    _load_env_file(local_env)
    external_prefixes = ("CAPITAL_", "CAPITALCOM_", "TRADING_", "POSTGRES_", "DATABASE_", "DB_")
    configured = os.getenv("CAPITAL_ENV_FILE")
    if configured:
        _load_env_file(Path(configured), allowed_prefixes=external_prefixes)


def _env_first(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _capital_api_base_default() -> str:
    configured = _env_first("CAPITALCOM_API_BASE", "CAPITAL_API_BASE_URL")
    if configured:
        return configured
    env_name = (os.getenv("CAPITAL_ENV", "demo") or "demo").strip().lower()
    return CAPITAL_LIVE_BASE_URL if env_name == "live" else CAPITAL_DEMO_BASE_URL


def _resource_path_env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if os.getenv("NEWXAU_RESOURCE_ROOT"):
        return str(resolve_resource_path(value))
    return value


def _runtime_path_env(name: str, default: str) -> str:
    value = os.getenv(name, default)
    if os.getenv("NEWXAU_RUNTIME_ROOT"):
        return str(resolve_runtime_path(value))
    return value


_load_runtime_env_files()


@dataclass(slots=True)
class RiskLimits:
    minimum_rr: float = 1.5
    preferred_rr: float = 2.0
    max_risk_per_trade_pct: float = 1.0
    max_daily_loss_pct: float = 3.0
    max_consecutive_losses: int = 3
    max_open_trades: int = 3
    max_spread: float = 0.40
    news_block_before_minutes: int = 30
    news_block_after_minutes: int = 15


@dataclass(slots=True)
class ModelWeights:
    weights: Dict[str, float] = field(
        default_factory=lambda: {
            "kronos": 0.30,
            "tcn": 0.25,
            "lightgbm": 0.20,
            "patchtst": 0.10,
            "cnn_lstm": 0.10,
            "nhits": 0.05,
        }
    )


@dataclass(slots=True)
class RuntimeConfig:
    instrument: str = field(default_factory=lambda: _env_first("TRADING_INSTRUMENT", "INSTRUMENT", default="XAUUSD") or "XAUUSD")
    cycle_timeframe: str = field(default_factory=lambda: _env_first("CYCLE_TIMEFRAME", default="5m") or "5m")
    supported_timeframes: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h")
    prediction_horizon_candles: int = field(default_factory=lambda: int(os.getenv("PREDICTION_HORIZON_CANDLES", "6")))
    min_model_confidence: float = 0.55
    data_provider: str = field(default_factory=lambda: os.getenv("DATA_PROVIDER", "capitalcom"))
    candle_csv_path: str | None = field(
        default_factory=lambda: (
            _resource_path_env("CANDLE_CSV_PATH", os.getenv("CANDLE_CSV_PATH", ""))
            if os.getenv("CANDLE_CSV_PATH")
            else None
        )
    )
    model_artifacts_dir: str = field(default_factory=lambda: _resource_path_env("MODEL_ARTIFACTS_DIR", "models"))
    postgres_dsn: str | None = field(default_factory=lambda: os.getenv("POSTGRES_DSN"))
    postgres_schema: str | None = field(default_factory=lambda: _env_first("POSTGRES_SCHEMA", "TRADING_DATABASE_SCHEMA"))
    live_cycle_interval_seconds: int = field(default_factory=lambda: int(os.getenv("LIVE_CYCLE_INTERVAL_SECONDS", "900")))
    live_candle_lookback: int = field(default_factory=lambda: int(os.getenv("LIVE_CANDLE_LOOKBACK", "900")))
    live_cycle_retry_attempts: int = field(default_factory=lambda: int(os.getenv("LIVE_CYCLE_RETRY_ATTEMPTS", "3")))
    live_cycle_retry_backoff_seconds: float = field(default_factory=lambda: float(os.getenv("LIVE_CYCLE_RETRY_BACKOFF_SECONDS", "2")))
    enable_data_quality_gate: bool = field(default_factory=lambda: _env_flag("ENABLE_DATA_QUALITY_GATE", False))
    data_quality_min_score: float = field(default_factory=lambda: float(os.getenv("DATA_QUALITY_MIN_SCORE", "85")))
    data_quality_max_missing_ratio: float = field(
        default_factory=lambda: float(os.getenv("DATA_QUALITY_MAX_MISSING_RATIO", "0.02"))
    )
    data_quality_max_outlier_ratio: float = field(
        default_factory=lambda: float(os.getenv("DATA_QUALITY_MAX_OUTLIER_RATIO", "0.01"))
    )
    data_quality_freshness_multiplier: float = field(
        default_factory=lambda: float(os.getenv("DATA_QUALITY_FRESHNESS_MULTIPLIER", "2.5"))
    )
    reports_dir: str = field(default_factory=lambda: _runtime_path_env("REPORTS_DIR", "reports"))
    strategy_version: str = field(default_factory=lambda: os.getenv("STRATEGY_VERSION", "strategy_v1"))
    threshold_profile_name: str = field(default_factory=lambda: os.getenv("THRESHOLD_PROFILE_NAME", "default"))
    minimum_final_confidence: float = field(default_factory=lambda: float(os.getenv("MINIMUM_FINAL_CONFIDENCE", "0.55")))
    recommended_score: float = field(default_factory=lambda: float(os.getenv("RECOMMENDED_SCORE", "75")))
    weak_recommendation_score: float = field(default_factory=lambda: float(os.getenv("WEAK_RECOMMENDATION_SCORE", "60")))
    minimum_risk_reward: float = field(default_factory=lambda: float(os.getenv("MINIMUM_RISK_REWARD", "1.5")))
    minimum_model_agreement: float = field(default_factory=lambda: float(os.getenv("MINIMUM_MODEL_AGREEMENT", "0.55")))
    atr_minimum: float = field(default_factory=lambda: float(os.getenv("ATR_MINIMUM", "0.1")))
    atr_maximum: float = field(default_factory=lambda: float(os.getenv("ATR_MAXIMUM", "1000")))
    adx_threshold: float = field(default_factory=lambda: float(os.getenv("ADX_THRESHOLD", "20")))
    news_provider_mode: str = field(default_factory=lambda: os.getenv("NEWS_PROVIDER_MODE", "manual"))
    news_provider_url: str | None = field(default_factory=lambda: os.getenv("NEWS_PROVIDER_URL"))
    news_block_before_minutes: int = field(default_factory=lambda: int(os.getenv("NEWS_BLOCK_BEFORE_MINUTES", "30")))
    news_block_after_minutes: int = field(default_factory=lambda: int(os.getenv("NEWS_BLOCK_AFTER_MINUTES", "30")))
    news_block_mode: str = field(default_factory=lambda: os.getenv("NEWS_BLOCK_MODE", "block"))
    model_weight_min: float = field(default_factory=lambda: float(os.getenv("MODEL_WEIGHT_MIN", "0.01")))
    model_weight_max: float = field(default_factory=lambda: float(os.getenv("MODEL_WEIGHT_MAX", "0.60")))
    model_weight_max_change_per_update: float = field(default_factory=lambda: float(os.getenv("MODEL_WEIGHT_MAX_CHANGE_PER_UPDATE", "0.03")))
    model_weight_performance_window: int = field(default_factory=lambda: int(os.getenv("MODEL_WEIGHT_PERFORMANCE_WINDOW", "100")))
    enable_dynamic_model_weights: bool = field(
        default_factory=lambda: os.getenv("ENABLE_DYNAMIC_MODEL_WEIGHTS", "1") in ("1", "true", "TRUE", "yes", "YES")
    )
    # Weight each model's ensemble vote by its own conviction (max class probability)
    # in addition to its configured weight. Calibration shows confident predictions are
    # more accurate, so this amplifies meaningful signals and mutes near-uniform ones.
    enable_confidence_weighting: bool = field(
        default_factory=lambda: _env_flag("ENABLE_CONFIDENCE_WEIGHTING", True)
    )
    min_observations_for_reweight: int = field(default_factory=lambda: int(os.getenv("MIN_OBSERVATIONS_FOR_REWEIGHT", "10")))
    enable_background_cycle_runner: bool = field(
        default_factory=lambda: os.getenv("ENABLE_BACKGROUND_CYCLE_RUNNER", "1") in ("1", "true", "TRUE", "yes", "YES")
    )
    enable_live_price_stream: bool = field(
        default_factory=lambda: os.getenv("ENABLE_LIVE_PRICE_STREAM", "1") in ("1", "true", "TRUE", "yes", "YES")
    )
    market_close_pause_enabled: bool = field(default_factory=lambda: _env_flag("MARKET_CLOSE_PAUSE_ENABLED", False))
    market_hours_timezone: str = field(default_factory=lambda: os.getenv("MARKET_HOURS_TIMEZONE", "UTC"))
    market_weekly_open: str = field(default_factory=lambda: os.getenv("MARKET_WEEKLY_OPEN", "SUN 22:00"))
    market_weekly_close: str = field(default_factory=lambda: os.getenv("MARKET_WEEKLY_CLOSE", "FRI 21:00"))
    market_daily_break_enabled: bool = field(default_factory=lambda: _env_flag("MARKET_DAILY_BREAK_ENABLED", False))
    market_daily_break_start: str = field(default_factory=lambda: os.getenv("MARKET_DAILY_BREAK_START", "21:00"))
    market_daily_break_end: str = field(default_factory=lambda: os.getenv("MARKET_DAILY_BREAK_END", "22:00"))
    market_supervisor_interval_seconds: int = field(default_factory=lambda: int(os.getenv("MARKET_SUPERVISOR_INTERVAL_SECONDS", "60")))
    market_close_backtest_enabled: bool = field(default_factory=lambda: _env_flag("MARKET_CLOSE_BACKTEST_ENABLED", False))
    market_close_backtest_synthetic_count: int = field(default_factory=lambda: int(os.getenv("MARKET_CLOSE_BACKTEST_SYNTHETIC_COUNT", "120")))
    market_close_backtest_train_size: int = field(default_factory=lambda: int(os.getenv("MARKET_CLOSE_BACKTEST_TRAIN_SIZE", "90")))
    market_close_backtest_test_size: int = field(default_factory=lambda: int(os.getenv("MARKET_CLOSE_BACKTEST_TEST_SIZE", "20")))
    market_close_backtest_step_size: int = field(default_factory=lambda: int(os.getenv("MARKET_CLOSE_BACKTEST_STEP_SIZE", "20")))
    market_close_backtest_min_window: int = field(default_factory=lambda: int(os.getenv("MARKET_CLOSE_BACKTEST_MIN_WINDOW", "80")))
    market_close_backtest_timeout_seconds: int = field(default_factory=lambda: int(os.getenv("MARKET_CLOSE_BACKTEST_TIMEOUT_SECONDS", "180")))
    websocket_heartbeat_seconds: int = field(default_factory=lambda: int(os.getenv("WEBSOCKET_HEARTBEAT_SECONDS", "30")))
    latest_price_stale_seconds: int = field(default_factory=lambda: int(os.getenv("LATEST_PRICE_STALE_SECONDS", "120")))
    capitalcom_stream_url: str = field(
        default_factory=lambda: os.getenv("CAPITALCOM_STREAM_URL", "wss://api-streaming-capital.backend-capital.com/connect")
    )
    capitalcom_stream_retry_seconds: int = field(default_factory=lambda: int(os.getenv("CAPITALCOM_STREAM_RETRY_SECONDS", "5")))
    capitalcom_stream_ping_seconds: int = field(default_factory=lambda: int(os.getenv("CAPITALCOM_STREAM_PING_SECONDS", "540")))
    enable_telegram_alerts: bool = field(
        default_factory=lambda: os.getenv("ENABLE_TELEGRAM_ALERTS", "0") in ("1", "true", "TRUE", "yes", "YES")
    )
    telegram_bot_token: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))

    # Capital.com broker connection settings.
    capitalcom_api_base: str = field(default_factory=_capital_api_base_default)
    capitalcom_api_key: str | None = field(default_factory=lambda: _env_first("CAPITALCOM_API_KEY", "CAPITAL_API_KEY"))
    capitalcom_identifier: str | None = field(default_factory=lambda: _env_first("CAPITALCOM_IDENTIFIER", "CAPITAL_IDENTIFIER", "CAPITAL_EMAIL"))
    capitalcom_password: str | None = field(default_factory=lambda: _env_first("CAPITALCOM_PASSWORD", "CAPITAL_PASSWORD"))
    capitalcom_epic: str = field(
        default_factory=lambda: _env_first("CAPITALCOM_EPIC", "CAPITAL_DEFAULT_EPIC", "TRADING_PROVIDER_SYMBOL", default="XAUUSD")
        or "XAUUSD"
    )
    capitalcom_price_side: str = field(default_factory=lambda: _env_first("CAPITALCOM_PRICE_SIDE", "CAPITAL_DEFAULT_PRICE_SIDE", default="mid") or "mid")
    capitalcom_use_encrypted_password: bool = field(default_factory=lambda: _env_flag("CAPITAL_USE_ENCRYPTED_PASSWORD", False))
    capital_execution_enabled: bool = field(default_factory=lambda: _env_flag("CAPITAL_EXECUTION_ENABLED", False))
    capital_execution_auto_execute: bool = field(default_factory=lambda: _env_flag("CAPITAL_EXECUTION_AUTO_EXECUTE", False))
    capital_execution_demo_only: bool = field(default_factory=lambda: _env_flag("CAPITAL_EXECUTION_DEMO_ONLY", True))
    capital_execution_account_name: str = field(default_factory=lambda: _env_first("CAPITAL_EXECUTION_ACCOUNT_NAME", "CAPITAL_ACCOUNT_NAME", default="NEWXAU") or "NEWXAU")
    capital_execution_default_size: float = field(default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_DEFAULT_SIZE", "0.01")))
    capital_execution_max_size: float = field(default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_MAX_SIZE", "0.10")))
    capital_execution_min_size: float = field(default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_MIN_SIZE", "0.01")))
    capital_execution_size_step: float = field(default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_SIZE_STEP", "0.01")))
    capital_execution_max_open_positions: int = field(default_factory=lambda: int(os.getenv("CAPITAL_EXECUTION_MAX_OPEN_POSITIONS", "1")))
    capital_execution_max_price_deviation: float = field(default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_MAX_PRICE_DEVIATION", "3.0")))
    capital_execution_confirm_attempts: int = field(default_factory=lambda: int(os.getenv("CAPITAL_EXECUTION_CONFIRM_ATTEMPTS", "3")))
    capital_execution_confirm_delay_seconds: float = field(default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_CONFIRM_DELAY_SECONDS", "0.35")))
    capital_execution_force_open: bool = field(default_factory=lambda: _env_flag("CAPITAL_EXECUTION_FORCE_OPEN", False))
    capital_execution_currency_code: str = field(default_factory=lambda: os.getenv("CAPITAL_EXECUTION_CURRENCY_CODE", "USD"))
    capital_execution_allowed_statuses: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            item.strip().upper()
            for item in os.getenv("CAPITAL_EXECUTION_ALLOWED_STATUSES", "RECOMMENDED").split(",")
            if item.strip()
        )
    )
    # Minimum final confidence (0-1) a recommendation must reach to be executed. 0 disables the gate.
    capital_execution_min_confidence: float = field(
        default_factory=lambda: float(os.getenv("CAPITAL_EXECUTION_MIN_CONFIDENCE", "0") or 0.0)
    )

    # News Intelligence settings
    news_collection_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_COLLECTION_ENABLED", True))
    news_ai_analysis_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_AI_ANALYSIS_ENABLED", True))
    news_strategy_weight_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_STRATEGY_WEIGHT_ENABLED", False))
    news_trade_block_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_TRADE_BLOCK_ENABLED", False))
    news_risk_reduction_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_RISK_REDUCTION_ENABLED", False))
    news_dashboard_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_DASHBOARD_ENABLED", True))
    news_shadow_mode: bool = field(default_factory=lambda: _env_flag("NEWS_SHADOW_MODE", True))
    news_max_weight_normal: float = field(default_factory=lambda: float(os.getenv("NEWS_MAX_WEIGHT_NORMAL", "0.20")))
    news_max_weight_high_impact: float = field(default_factory=lambda: float(os.getenv("NEWS_MAX_WEIGHT_HIGH_IMPACT", "0.35")))
    news_max_position_multiplier: float = field(default_factory=lambda: float(os.getenv("NEWS_MAX_POSITION_MULTIPLIER", "1.05")))
    news_conflict_size_multiplier: float = field(default_factory=lambda: float(os.getenv("NEWS_CONFLICT_SIZE_MULTIPLIER", "0.50")))
    news_default_validity_minutes: int = field(default_factory=lambda: int(os.getenv("NEWS_DEFAULT_VALIDITY_MINUTES", "240")))
    news_min_ai_confidence: float = field(default_factory=lambda: float(os.getenv("NEWS_MIN_AI_CONFIDENCE", "0.65")))
    news_min_relevance_to_analyze: str = field(default_factory=lambda: os.getenv("NEWS_MIN_RELEVANCE_TO_ANALYZE", "MEDIUM"))
    news_rss_urls: str = field(default_factory=lambda: os.getenv("NEWS_RSS_URLS", ""))
    news_capital_related_enabled: bool = field(default_factory=lambda: _env_flag("NEWS_CAPITAL_RELATED_ENABLED", False))
    news_capital_session_state_path: str | None = field(default_factory=lambda: os.getenv("NEWS_CAPITAL_SESSION_STATE_PATH"))
    news_capital_exported_news_path: str | None = field(default_factory=lambda: os.getenv("NEWS_CAPITAL_EXPORTED_NEWS_PATH"))
    news_capital_platform_url: str = field(default_factory=lambda: os.getenv("NEWS_CAPITAL_PLATFORM_URL", "https://capital.com/trading/platform"))
    news_capital_playwright_headless: bool = field(default_factory=lambda: _env_flag("NEWS_CAPITAL_PLAYWRIGHT_HEADLESS", True))
    enable_news_intelligence: bool = field(default_factory=lambda: _env_flag("ENABLE_NEWS_INTELLIGENCE", True))
