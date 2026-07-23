from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .market_sessions import GOLD_MARKET_SESSION_NAMES, default_gold_session_permissions, normalize_gold_session_name


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RecommendationStatus(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    WEAK_RECOMMENDATION = "WEAK_RECOMMENDATION"
    HOLD = "HOLD"
    BLOCKED_BY_LOW_CONFIDENCE = "BLOCKED_BY_LOW_CONFIDENCE"
    BLOCKED_BY_MODEL_CONFLICT = "BLOCKED_BY_MODEL_CONFLICT"
    BLOCKED_BY_RISK = "BLOCKED_BY_RISK"
    BLOCKED_BY_SPREAD = "BLOCKED_BY_SPREAD"
    BLOCKED_BY_NEWS = "BLOCKED_BY_NEWS"
    BLOCKED_BY_LOW_RR = "BLOCKED_BY_LOW_RR"
    BLOCKED_BY_LOW_RISK_REWARD = "BLOCKED_BY_LOW_RISK_REWARD"
    BLOCKED_BY_BAD_ENTRY = "BLOCKED_BY_BAD_ENTRY"
    BLOCKED_BY_MARKET_STRUCTURE = "BLOCKED_BY_MARKET_STRUCTURE"
    BLOCKED_BY_SYSTEM_HEALTH = "BLOCKED_BY_SYSTEM_HEALTH"
    BLOCKED_NO_VALID_ENTRY_PLAN = "BLOCKED_NO_VALID_ENTRY_PLAN"
    BLOCKED_LOW_RISK_REWARD = "BLOCKED_LOW_RISK_REWARD"
    BLOCKED_SL_TOO_WIDE = "BLOCKED_SL_TOO_WIDE"
    BLOCKED_SL_TOO_TIGHT = "BLOCKED_SL_TOO_TIGHT"


class AgreementStatus(str, Enum):
    STRONG = "STRONG"
    NORMAL = "NORMAL"
    MIXED = "MIXED"
    HIGH_CONFLICT = "HIGH_CONFLICT"


class RiskStatus(str, Enum):
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"


class EntryType(str, Enum):
    MARKET = "MARKET"
    LIMIT_PULLBACK = "LIMIT_PULLBACK"
    BREAKOUT = "BREAKOUT"
    RETEST = "RETEST"
    REVERSAL = "REVERSAL"
    SMC_IFVG = "SMC_IFVG"
    NONE = "NONE"


EXECUTION_CONTROL_SESSIONS: tuple[str, ...] = GOLD_MARKET_SESSION_NAMES
EXECUTION_CONTROL_DIRECTIONS: tuple[str, ...] = ("BUY", "SELL")


def normalize_execution_session_name(value: Any) -> str:
    return normalize_gold_session_name(value)


def default_execution_direction_permissions() -> dict[str, bool]:
    return {direction: True for direction in EXECUTION_CONTROL_DIRECTIONS}


def normalize_execution_direction(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text in EXECUTION_CONTROL_DIRECTIONS else "UNKNOWN"


class ExecutionControlConfig(BaseModel):
    enabled: bool = True
    allowed_sessions: dict[str, bool] = Field(
        default_factory=default_gold_session_permissions
    )
    allowed_directions: dict[str, bool] = Field(
        default_factory=default_execution_direction_permissions
    )
    require_ensemble_opposite_or_tie: bool = False
    apply_to_auto: bool = True
    apply_to_manual: bool = True
    tie_policy: str = "directional_vote_tie"

    @field_validator("allowed_sessions", mode="before")
    @classmethod
    def normalize_allowed_sessions(cls, value: Any) -> dict[str, bool]:
        allowed = default_gold_session_permissions()
        if not isinstance(value, dict):
            return allowed
        for key, raw_enabled in value.items():
            session = normalize_execution_session_name(key)
            if session in EXECUTION_CONTROL_SESSIONS:
                allowed[session] = bool(raw_enabled)
        return allowed

    @field_validator("allowed_directions", mode="before")
    @classmethod
    def normalize_allowed_directions(cls, value: Any) -> dict[str, bool]:
        allowed = default_execution_direction_permissions()
        if not isinstance(value, dict):
            return allowed
        for key, raw_enabled in value.items():
            direction = normalize_execution_direction(key)
            if direction in EXECUTION_CONTROL_DIRECTIONS:
                allowed[direction] = bool(raw_enabled)
        return allowed

    @field_validator("tie_policy", mode="after")
    @classmethod
    def validate_tie_policy(cls, value: str) -> str:
        normalized = str(value or "directional_vote_tie").strip().lower()
        if normalized != "directional_vote_tie":
            raise ValueError("tie_policy must be directional_vote_tie")
        return normalized


class ExecutionControlDecision(BaseModel):
    signal_id: Optional[int] = None
    source: str = "manual"
    source_kind: str = "manual"
    applied: bool = True
    allowed: bool
    reason: str
    session_name: str = "UNKNOWN"
    ensemble_signal: Optional[str] = None
    kronos_signal: Optional[str] = None
    kronos_relation: str = "UNKNOWN"
    directional_vote_tie: bool = False
    buy_votes: int = 0
    sell_votes: int = 0
    hold_votes: int = 0
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class Candle(BaseModel):
    instrument: str
    timeframe: str
    candle_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    @model_validator(mode="after")
    def validate_ohlc(self) -> "Candle":
        if self.high < self.open:
            raise ValueError("high must be >= open")
        if self.high < self.close:
            raise ValueError("high must be >= close")
        if self.low > self.open:
            raise ValueError("low must be <= open")
        if self.low > self.close:
            raise ValueError("low must be <= close")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        return self


class DataQualityReport(BaseModel):
    total_rows: int
    cleaned_rows: int
    duplicate_rows: int
    invalid_rows: int
    missing_candles_count: int
    missing_timestamps: list[datetime] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=100.0, ge=0.0, le=100.0)
    freshness_seconds: Optional[float] = Field(default=None, ge=0.0)
    missing_candles: int = 0
    duplicate_candles: int = 0
    outlier_count: int = 0
    out_of_order_count: int = 0
    spread_status: str = "NOT_EVALUATED"
    aggregation_status: str = "NOT_EVALUATED"
    provider_status: str = "UNKNOWN"
    gate_status: str = "MONITOR_ONLY"
    blocking_reasons: list[str] = Field(default_factory=list)


class IndicatorGroupScore(BaseModel):
    bias: str
    score: float = Field(ge=0.0, le=100.0)


class FVG(BaseModel):
    timeframe: str
    is_bullish: bool
    top: float
    bottom: float
    mitigated: bool
    created_time: datetime
    mitigated_time: Optional[datetime] = None


class LiquidityLevel(BaseModel):
    level_type: str  # PDH, PDL, ASIAN_HIGH, ASIAN_LOW, EQUAL_HIGH, EQUAL_LOW, 4H_HIGH, 4H_LOW
    price: float
    created_time: datetime


class LiquiditySweep(BaseModel):
    level: LiquidityLevel
    sweep_time: datetime
    rejected: bool


class SMCSnapshot(BaseModel):
    active_htf_fvgs: list[FVG] = Field(default_factory=list)
    recent_sweeps: list[LiquiditySweep] = Field(default_factory=list)
    active_ifvgs: list[FVG] = Field(default_factory=list)
    dol: Optional[LiquidityLevel] = None
    is_po3_time: bool = False
    smc_setup_valid: bool = False
    setup_direction: Optional[SignalDirection] = None


class IndicatorSnapshot(BaseModel):
    instrument: str
    timeframe: str
    snapshot_time: datetime
    trend: IndicatorGroupScore
    momentum: IndicatorGroupScore
    volatility_status: str
    atr: float
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    structure_bias: str
    session_name: str
    news_status: str
    raw_json: dict[str, Any] = Field(default_factory=dict)
    smc: Optional[SMCSnapshot] = None


class ModelPrediction(BaseModel):
    model_name: str
    model_version: str
    instrument: str
    timeframe: str
    prediction_time: datetime
    signal: SignalDirection
    buy_probability: float
    sell_probability: float
    hold_probability: float
    confidence: float
    expected_return: float
    expected_range: float
    prediction_horizon_candles: int

    @field_validator(
        "buy_probability",
        "sell_probability",
        "hold_probability",
        "confidence",
        mode="after",
    )
    @classmethod
    def validate_probability(cls, value: float) -> float:
        if value < 0.0 or value > 1.0:
            raise ValueError("probability/confidence values must be in [0, 1]")
        return value


class EnsemblePrediction(BaseModel):
    instrument: str
    timeframe: str
    prediction_time: datetime
    ensemble_signal: SignalDirection
    ensemble_confidence: float
    buy_score: float
    sell_score: float
    hold_score: float
    agreement_status: AgreementStatus
    active_models: list[str]
    conflicting_models: list[str]
    summary: str


class StrategyDecision(BaseModel):
    instrument: str
    timeframe: str
    signal: SignalDirection
    status: RecommendationStatus
    score: float
    confidence: float
    strategy_bias: str
    model_consensus: str
    indicator_bias: str
    entry_quality: str
    risk_status: str
    reasons: list[str]
    blocked_reasons: list[str]
    news_state_id: Optional[int] = None
    news_bias: Optional[str] = None
    news_confidence: Optional[float] = None
    news_weight_used: Optional[float] = None
    news_action_level: Optional[str] = None
    news_block_reason: Optional[str] = None
    final_score_before_news: Optional[float] = None
    final_score_after_news: Optional[float] = None


class TradePlan(BaseModel):
    entry_type: EntryType
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk: float
    reward: float
    risk_reward: float
    entry_quality_score: float
    valid_for_minutes: int
    sl_method: str
    tp_method: str
    reason: str


class RiskCheck(BaseModel):
    risk_status: RiskStatus
    risk_reward: float
    spread_status: str
    spread: float
    max_allowed_spread: float
    news_status: str
    volatility_status: str
    position_size_status: str
    blocked_reasons: list[str] = Field(default_factory=list)


class FinalRecommendation(BaseModel):
    instrument: str
    timeframe: str
    signal_time: datetime
    signal: SignalDirection
    status: RecommendationStatus
    confidence: float
    score: float
    entry_type: Optional[EntryType] = None
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    risk_amount: Optional[float] = None
    reward_amount: Optional[float] = None
    risk_reward: Optional[float] = None
    risk_level: str = "NO_TRADE"
    valid_for_minutes: Optional[int] = None
    model_consensus: str
    indicator_bias: str
    risk_status: str
    reasons: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    model_votes: list[ModelPrediction] = Field(default_factory=list)
    indicator_summary: dict[str, Any] = Field(default_factory=dict)
    expiry_time: Optional[datetime] = None
    outcome_status: str = "PENDING"
    entry_triggered: bool = False
    outcome_validated_at: Optional[datetime] = None
    realized_rr: Optional[float] = None
    max_favorable_move: Optional[float] = None
    max_adverse_move: Optional[float] = None
    strategy_version: str = "strategy_v1"
    threshold_profile_id: Optional[int] = None
    model_weight_profile_id: Optional[int] = None
    validation_timeline: list[dict[str, Any]] = Field(default_factory=list)
    news_state_id: Optional[int] = None
    news_bias: Optional[str] = None
    news_confidence: Optional[float] = None
    news_weight_used: Optional[float] = None
    news_action_level: Optional[str] = None
    news_block_reason: Optional[str] = None
    final_score_before_news: Optional[float] = None
    final_score_after_news: Optional[float] = None


class MarketContext(BaseModel):
    spread: float = 0.25
    news_status: str = "CLEAR"
    minutes_to_high_impact_news: Optional[int] = None
    minutes_since_high_impact_news: Optional[int] = None
    daily_loss_percent: float = 0.0
    consecutive_losses: int = 0
    open_recommendations: int = 0
    special_volatility_mode: bool = False
