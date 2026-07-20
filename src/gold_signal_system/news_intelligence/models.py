from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    CPI = "CPI"
    FOMC_RATE_DECISION = "FOMC_RATE_DECISION"
    FOMC_MINUTES = "FOMC_MINUTES"
    NFP = "NFP"
    FED_SPEECH = "FED_SPEECH"
    WAR_ESCALATION = "WAR_ESCALATION"
    GEOPOLITICAL_RISK = "GEOPOLITICAL_RISK"
    PPI = "PPI"
    JOBLESS_CLAIMS = "JOBLESS_CLAIMS"
    RETAIL_SALES = "RETAIL_SALES"
    ISM_PMI = "ISM_PMI"
    GENERAL_GOLD_NEWS = "GENERAL_GOLD_NEWS"
    UNKNOWN = "UNKNOWN"


class NewsRelevance(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class NewsDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class TradeBias(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class ImpactStrength(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class VolatilityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class ActionLevel(str, Enum):
    INFO_ONLY = "INFO_ONLY"
    WEIGHT_ONLY = "WEIGHT_ONLY"
    RISK_REDUCE = "RISK_REDUCE"
    BLOCK_NEW_TRADES = "BLOCK_NEW_TRADES"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class SourceHealthStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class RecommendedStrategyAction(BaseModel):
    news_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    max_position_multiplier: float = Field(default=1.0, ge=0.0, le=2.0)
    valid_until_minutes: int = Field(default=0, ge=0, le=1440)


class NormalizedNewsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instrument: str
    source: str = "manual"
    title: str
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    url: str | None = None
    raw_text: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    event_type: str = EventType.GENERAL_GOLD_NEWS.value
    relevance: str = NewsRelevance.UNKNOWN.value

    @field_validator("instrument", "source", "title", mode="before")
    @classmethod
    def _strip_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("value cannot be empty")
        return text

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        value = str(value or EventType.UNKNOWN.value).upper()
        return value if value in EventType._value2member_map_ else EventType.UNKNOWN.value

    @field_validator("relevance")
    @classmethod
    def _validate_relevance(cls, value: str) -> str:
        value = str(value or NewsRelevance.UNKNOWN.value).upper()
        return value if value in NewsRelevance._value2member_map_ else NewsRelevance.UNKNOWN.value


class MacroEventModel(BaseModel):
    event_type: str
    title: str
    country: str | None = "US"
    currency: str | None = "USD"
    scheduled_at: datetime
    importance: str
    forecast_value: str | None = None
    previous_value: str | None = None
    actual_value: str | None = None
    source: str | None = "manual_calendar"
    url: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "SCHEDULED"

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        value = str(value or EventType.UNKNOWN.value).upper()
        return value if value in EventType._value2member_map_ else EventType.UNKNOWN.value

    @field_validator("importance")
    @classmethod
    def _validate_importance(cls, value: str) -> str:
        value = str(value or "MEDIUM").upper()
        return value if value in {"LOW", "MEDIUM", "HIGH", "CRITICAL"} else "MEDIUM"

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        value = str(value or "SCHEDULED").upper()
        return value if value in {"SCHEDULED", "RELEASED", "CANCELLED", "UPDATED"} else "SCHEDULED"


class NewsAiAnalysisModel(BaseModel):
    instrument: str
    event_type: str
    news_relevance: str
    direction: str
    trade_bias: str
    confidence: float = Field(ge=0.0, le=1.0)
    impact_strength: str
    expected_time_window: str
    market_session: str
    volatility_expected: str
    risk_level: str
    action_level: str
    should_block_trading: bool = False
    should_reduce_position_size: bool = False
    summary: str
    reasoning_points: list[str] = Field(default_factory=list)
    recommended_strategy_action: RecommendedStrategyAction = Field(default_factory=RecommendedStrategyAction)
    raw_ai_response: dict[str, Any] = Field(default_factory=dict)
    valid_until: datetime | None = None

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, value: str) -> str:
        value = str(value or EventType.UNKNOWN.value).upper()
        return value if value in EventType._value2member_map_ else EventType.UNKNOWN.value

    @field_validator("news_relevance")
    @classmethod
    def _validate_relevance(cls, value: str) -> str:
        value = str(value or NewsRelevance.UNKNOWN.value).upper()
        return value if value in NewsRelevance._value2member_map_ else NewsRelevance.UNKNOWN.value

    @field_validator("direction")
    @classmethod
    def _validate_direction(cls, value: str) -> str:
        value = str(value or NewsDirection.UNKNOWN.value).upper()
        return value if value in NewsDirection._value2member_map_ else NewsDirection.UNKNOWN.value

    @field_validator("trade_bias")
    @classmethod
    def _validate_trade_bias(cls, value: str) -> str:
        value = str(value or TradeBias.HOLD.value).upper()
        return value if value in TradeBias._value2member_map_ else TradeBias.HOLD.value

    @field_validator("impact_strength")
    @classmethod
    def _validate_impact(cls, value: str) -> str:
        value = str(value or ImpactStrength.LOW.value).upper()
        return value if value in ImpactStrength._value2member_map_ else ImpactStrength.LOW.value

    @field_validator("volatility_expected")
    @classmethod
    def _validate_volatility(cls, value: str) -> str:
        value = str(value or VolatilityLevel.MEDIUM.value).upper()
        return value if value in VolatilityLevel._value2member_map_ else VolatilityLevel.MEDIUM.value

    @field_validator("risk_level")
    @classmethod
    def _validate_risk(cls, value: str) -> str:
        value = str(value or RiskLevel.MEDIUM.value).upper()
        return value if value in RiskLevel._value2member_map_ else RiskLevel.MEDIUM.value

    @field_validator("action_level")
    @classmethod
    def _validate_action(cls, value: str) -> str:
        value = str(value or ActionLevel.INFO_ONLY.value).upper()
        return value if value in ActionLevel._value2member_map_ else ActionLevel.INFO_ONLY.value

    @model_validator(mode="after")
    def _derive_valid_until(self) -> "NewsAiAnalysisModel":
        if self.valid_until is None and self.recommended_strategy_action.valid_until_minutes:
            self.valid_until = datetime.now(tz=UTC) + timedelta(minutes=self.recommended_strategy_action.valid_until_minutes)
        return self


class StrategyNewsStateModel(BaseModel):
    id: int | None = None
    instrument: str
    active_direction: str
    active_trade_bias: str
    active_confidence: float = Field(ge=0.0, le=1.0)
    active_news_weight: float = Field(ge=0.0, le=1.0)
    block_trading: bool = False
    reduce_position_size: bool = False
    action_level: str
    reason: str
    active_event_type: str
    valid_until: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class NewsSourceHealthModel(BaseModel):
    source: str
    status: str = SourceHealthStatus.UNKNOWN.value
    last_success_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class NewsImpactValidationModel(BaseModel):
    analysis_id: int
    instrument: str
    horizon_minutes: int
    predicted_direction: str
    actual_direction: str
    price_at_analysis: float
    price_at_horizon: float
    return_pct: float
    was_correct: bool
    notes: str | None = None
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
