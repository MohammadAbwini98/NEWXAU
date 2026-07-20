from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import os
import re
from typing import Any

import requests
from pydantic import ValidationError

from .collectors import classify_event_type, classify_relevance
from .models import (
    ActionLevel,
    EventType,
    ImpactStrength,
    MacroEventModel,
    NewsAiAnalysisModel,
    NewsDirection,
    NewsRelevance,
    NormalizedNewsItem,
    RecommendedStrategyAction,
    RiskLevel,
    TradeBias,
    VolatilityLevel,
)
from ..market_sessions import get_gold_market_session

logger = logging.getLogger(__name__)


SCHEMA_TEXT = """{
  "instrument": "XAUUSD",
  "news_relevance": "LOW|MEDIUM|HIGH|CRITICAL",
  "direction": "UP|DOWN|NEUTRAL|MIXED|UNKNOWN",
  "trade_bias": "BUY|SELL|HOLD|NO_TRADE",
  "confidence": 0.0,
  "impact_strength": "LOW|MEDIUM|HIGH|EXTREME",
  "expected_time_window": "string",
  "market_session": "ASIA_LOW|LONDON_ACTIVE|US_OVERLAP|NY_ACTIVE|DAILY_BREAK|UNKNOWN",
  "volatility_expected": "LOW|MEDIUM|HIGH|EXTREME",
  "risk_level": "LOW|MEDIUM|HIGH|EXTREME",
  "action_level": "INFO_ONLY|WEIGHT_ONLY|RISK_REDUCE|BLOCK_NEW_TRADES|MANUAL_REVIEW",
  "should_block_trading": false,
  "should_reduce_position_size": false,
  "summary": "string",
  "reasoning_points": [],
  "recommended_strategy_action": {
    "news_weight": 0.0,
    "max_position_multiplier": 1.0,
    "valid_until_minutes": 0
  }
}"""


class AiNewsAnalyzer:
    """Strict news impact analyzer with optional external AI provider and safe fallback."""

    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.provider = (os.getenv("NEWS_AI_PROVIDER", "rules") or "rules").strip().lower()
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("NEWS_AI_API_KEY")
        self.model = os.getenv("NEWS_AI_MODEL", "gpt-4.1-mini")
        self.endpoint = os.getenv("NEWS_AI_ENDPOINT", "https://api.openai.com/v1/chat/completions")

    def analyze_news_item(self, item: NormalizedNewsItem) -> NewsAiAnalysisModel | None:
        prompt = self.build_prompt(
            title=item.title,
            source=item.source,
            time=item.published_at or item.collected_at,
            event_type=item.event_type,
            forecast_value=None,
            previous_value=None,
            actual_value=None,
            raw_text=item.raw_text,
        )
        return self._analyze_with_optional_provider(prompt, event_type=item.event_type, fallback=lambda: self._rules_for_news(item))

    def analyze_macro_event(self, event: MacroEventModel, instrument: str = "XAUUSD") -> NewsAiAnalysisModel | None:
        prompt = self.build_prompt(
            title=event.title,
            source=event.source or "macro_calendar",
            time=event.scheduled_at,
            event_type=event.event_type,
            forecast_value=event.forecast_value,
            previous_value=event.previous_value,
            actual_value=event.actual_value,
            raw_text=json.dumps(event.raw_payload or {}, default=str),
        )
        return self._analyze_with_optional_provider(prompt, event_type=event.event_type, fallback=lambda: self._rules_for_macro(event, instrument))

    def build_prompt(
        self,
        *,
        title: str,
        source: str,
        time: datetime | None,
        event_type: str,
        forecast_value: str | None,
        previous_value: str | None,
        actual_value: str | None,
        raw_text: str | None,
    ) -> str:
        additions = self._event_prompt_addition(event_type)
        return (
            "You are an XAUUSD market-news impact analyst for a trading decision-support system.\n\n"
            "Analyze the following news or macro event only for its likely impact on XAUUSD / Gold.\n"
            "Do not provide financial advice. Do not claim certainty. Return strict JSON only.\n\n"
            "Instrument: XAUUSD\n"
            "Current context:\n"
            "- Timeframe used by system: 5-minute candles\n"
            "- System uses KRONOS model + technical strategy + risk engine\n"
            "- Your output will be used as a news/risk weight, not as a direct trade command\n\n"
            "News/event:\n"
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"Published/Scheduled time: {time.isoformat() if isinstance(time, datetime) else time}\n"
            f"Event type: {event_type}\n"
            f"Forecast: {forecast_value}\n"
            f"Previous: {previous_value}\n"
            f"Actual: {actual_value}\n"
            f"Raw text: {(raw_text or '')[:4000]}\n\n"
            "Consider USD impact, Treasury yield impact, Fed rate expectations, safe-haven demand, "
            "inflation expectation, geopolitical risk, expected market session, and likely volatility window.\n"
            f"{additions}\n\n"
            f"Return JSON using exactly this schema:\n{SCHEMA_TEXT}"
        )

    def validate_ai_payload(self, payload: dict[str, Any], *, event_type: str, instrument: str = "XAUUSD") -> NewsAiAnalysisModel:
        raw_payload = dict(payload)
        normalized = {
            **payload,
            "instrument": instrument,
            "event_type": str(payload.get("event_type") or event_type or EventType.UNKNOWN.value).upper(),
        }
        action = normalized.get("recommended_strategy_action") or {}
        if not isinstance(action, dict):
            action = {}
        normalized["recommended_strategy_action"] = self._clamped_action(
            relevance=str(normalized.get("news_relevance") or NewsRelevance.UNKNOWN.value),
            action=action,
            high_impact=str(normalized.get("impact_strength") or "").upper() in {"HIGH", "EXTREME"},
        ).model_dump()
        normalized["confidence"] = max(0.0, min(1.0, float(normalized.get("confidence") or 0.0)))
        normalized["raw_ai_response"] = raw_payload
        return NewsAiAnalysisModel.model_validate(normalized)

    def parse_and_validate_response(self, text: str, *, event_type: str, instrument: str = "XAUUSD") -> NewsAiAnalysisModel:
        payload = self._extract_json(text)
        return self.validate_ai_payload(payload, event_type=event_type, instrument=instrument)

    def _analyze_with_optional_provider(self, prompt: str, *, event_type: str, fallback) -> NewsAiAnalysisModel | None:
        if self.provider in {"openai", "http"} and self.api_key:
            for attempt in range(2):
                try:
                    text = self._call_chat_completion(prompt)
                    return self.parse_and_validate_response(text, event_type=event_type)
                except Exception as exc:
                    logger.warning("AI news analyzer provider attempt %s failed: %s", attempt + 1, exc)
        try:
            return fallback()
        except Exception as exc:
            logger.error("Rules-based news analyzer fallback failed: %s", exc)
            return None

    def _call_chat_completion(self, prompt: str) -> str:
        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"])

    def _rules_for_news(self, item: NormalizedNewsItem) -> NewsAiAnalysisModel:
        content = f"{item.title} {item.raw_text or ''}".lower()
        relevance = item.relevance
        if relevance == NewsRelevance.UNKNOWN.value:
            relevance = classify_relevance(item.title, item.raw_text).value
        event_type = item.event_type if item.event_type != EventType.UNKNOWN.value else classify_event_type(item.title, item.raw_text)

        direction = NewsDirection.NEUTRAL
        trade_bias = TradeBias.HOLD
        confidence = 0.48
        impact = ImpactStrength.LOW
        volatility = VolatilityLevel.MEDIUM
        risk = RiskLevel.LOW
        action = ActionLevel.INFO_ONLY
        reduce = False
        block = False
        reasons = ["Rules-based fallback used because no validated AI provider response was available."]

        if any(word in content for word in ("war", "escalation", "missile", "strike", "invasion", "safe haven")):
            direction = NewsDirection.UP
            trade_bias = TradeBias.BUY
            confidence = 0.72
            impact = ImpactStrength.HIGH
            volatility = VolatilityLevel.HIGH
            risk = RiskLevel.HIGH
            action = ActionLevel.RISK_REDUCE
            reduce = True
            reasons.append("Geopolitical/safe-haven language is generally supportive for gold but volatile.")
        elif any(word in content for word in ("hot cpi", "higher inflation", "hawkish", "higher rates", "yields rise", "dollar rises")):
            direction = NewsDirection.DOWN
            trade_bias = TradeBias.SELL
            confidence = 0.66
            impact = ImpactStrength.MEDIUM
            risk = RiskLevel.MEDIUM
            action = ActionLevel.WEIGHT_ONLY
            reasons.append("Higher-rate or USD/yield-positive language is usually pressure for XAUUSD.")
        elif any(word in content for word in ("dovish", "rate cut", "lower yields", "dollar falls", "cooling inflation", "weak jobs")):
            direction = NewsDirection.UP
            trade_bias = TradeBias.BUY
            confidence = 0.66
            impact = ImpactStrength.MEDIUM
            risk = RiskLevel.MEDIUM
            action = ActionLevel.WEIGHT_ONLY
            reasons.append("Lower-rate or USD/yield-negative language is usually supportive for XAUUSD.")
        elif any(word in content for word in ("cpi", "fomc", "nfp", "fed")):
            direction = NewsDirection.MIXED
            trade_bias = TradeBias.NO_TRADE
            confidence = 0.62
            impact = ImpactStrength.HIGH
            volatility = VolatilityLevel.HIGH
            risk = RiskLevel.HIGH
            action = ActionLevel.RISK_REDUCE
            reduce = True
            reasons.append("High-impact macro language without clear actual-vs-forecast signal increases volatility risk.")

        if relevance in {NewsRelevance.LOW.value, NewsRelevance.UNKNOWN.value}:
            action = ActionLevel.INFO_ONLY
            reduce = False
            block = False

        strategy_action = self._clamped_action(
            relevance=relevance,
            action={
                "news_weight": self._suggested_weight(relevance, impact.value),
                "max_position_multiplier": 0.75 if reduce else 1.0,
                "valid_until_minutes": self._default_validity_minutes(),
            },
            high_impact=impact in {ImpactStrength.HIGH, ImpactStrength.EXTREME},
        )
        return NewsAiAnalysisModel(
            instrument=item.instrument,
            event_type=event_type,
            news_relevance=relevance,
            direction=direction.value,
            trade_bias=trade_bias.value,
            confidence=confidence,
            impact_strength=impact.value,
            expected_time_window="1-4 hours",
            market_session=self._session_for_time(item.published_at or item.collected_at),
            volatility_expected=volatility.value,
            risk_level=risk.value,
            action_level=action.value,
            should_block_trading=block,
            should_reduce_position_size=reduce,
            summary=self._summary_for(direction, trade_bias, risk, item.title),
            reasoning_points=reasons,
            recommended_strategy_action=strategy_action,
            raw_ai_response={"provider": "rules", "generated_at": datetime.now(tz=UTC).isoformat()},
        )

    def _rules_for_macro(self, event: MacroEventModel, instrument: str) -> NewsAiAnalysisModel:
        direction = NewsDirection.MIXED
        trade_bias = TradeBias.NO_TRADE
        confidence = 0.70
        summary_reason = "High-impact scheduled macro event increases XAUUSD volatility."
        if event.actual_value and event.forecast_value:
            actual = self._number(event.actual_value)
            forecast = self._number(event.forecast_value)
            if actual is not None and forecast is not None:
                if event.event_type in {EventType.CPI.value, EventType.PPI.value, EventType.NFP.value}:
                    if actual > forecast:
                        direction = NewsDirection.DOWN
                        trade_bias = TradeBias.SELL
                        summary_reason = "Actual value exceeded forecast; USD/yields may pressure gold."
                    elif actual < forecast:
                        direction = NewsDirection.UP
                        trade_bias = TradeBias.BUY
                        summary_reason = "Actual value missed forecast; lower rate expectations may support gold."
                    confidence = 0.76
        action = ActionLevel.BLOCK_NEW_TRADES if event.importance in {"HIGH", "CRITICAL"} else ActionLevel.RISK_REDUCE
        strategy_action = self._clamped_action(
            relevance=NewsRelevance.CRITICAL.value,
            action={
                "news_weight": self._max_weight(high_impact=True),
                "max_position_multiplier": 0.5,
                "valid_until_minutes": 120,
            },
            high_impact=True,
        )
        return NewsAiAnalysisModel(
            instrument=instrument,
            event_type=event.event_type,
            news_relevance=NewsRelevance.CRITICAL.value,
            direction=direction.value,
            trade_bias=trade_bias.value,
            confidence=confidence,
            impact_strength=ImpactStrength.HIGH.value,
            expected_time_window="30 minutes-2 hours",
            market_session=self._session_for_time(event.scheduled_at),
            volatility_expected=VolatilityLevel.HIGH.value,
            risk_level=RiskLevel.HIGH.value,
            action_level=action.value,
            should_block_trading=action == ActionLevel.BLOCK_NEW_TRADES,
            should_reduce_position_size=True,
            summary=summary_reason,
            reasoning_points=[
                "Scheduled high-impact USD macro event.",
                "Risk window handling remains subject to rollout flags.",
                "Risk engine remains final authority.",
            ],
            recommended_strategy_action=strategy_action,
            raw_ai_response={"provider": "rules", "generated_at": datetime.now(tz=UTC).isoformat()},
        )

    def _clamped_action(self, relevance: str, action: dict[str, Any], high_impact: bool) -> RecommendedStrategyAction:
        max_weight = min(self._weight_cap_for_relevance(relevance), self._max_weight(high_impact))
        return RecommendedStrategyAction(
            news_weight=max(0.0, min(float(action.get("news_weight") or 0.0), max_weight)),
            max_position_multiplier=max(0.0, min(float(action.get("max_position_multiplier") or 1.0), self._max_position_multiplier())),
            valid_until_minutes=int(action.get("valid_until_minutes") or self._default_validity_minutes()),
        )

    def _weight_cap_for_relevance(self, relevance: str) -> float:
        return {
            NewsRelevance.LOW.value: 0.0,
            NewsRelevance.UNKNOWN.value: 0.0,
            NewsRelevance.MEDIUM.value: 0.10,
            NewsRelevance.HIGH.value: 0.20,
            NewsRelevance.CRITICAL.value: 0.35,
        }.get(str(relevance).upper(), 0.0)

    def _max_weight(self, high_impact: bool) -> float:
        attr = "news_max_weight_high_impact" if high_impact else "news_max_weight_normal"
        return float(getattr(self.config, attr, 0.35 if high_impact else 0.20) if self.config else (0.35 if high_impact else 0.20))

    def _max_position_multiplier(self) -> float:
        return float(getattr(self.config, "news_max_position_multiplier", 1.05) if self.config else 1.05)

    def _default_validity_minutes(self) -> int:
        return int(getattr(self.config, "news_default_validity_minutes", 240) if self.config else 240)

    def _suggested_weight(self, relevance: str, impact: str) -> float:
        base = {NewsRelevance.MEDIUM.value: 0.08, NewsRelevance.HIGH.value: 0.16, NewsRelevance.CRITICAL.value: 0.25}.get(relevance, 0.0)
        mult = {ImpactStrength.LOW.value: 0.4, ImpactStrength.MEDIUM.value: 0.7, ImpactStrength.HIGH.value: 1.0, ImpactStrength.EXTREME.value: 1.2}.get(impact, 0.5)
        return base * mult

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

    @staticmethod
    def _number(text: str) -> float | None:
        match = re.search(r"-?\d+(?:\.\d+)?", str(text))
        return float(match.group(0)) if match else None

    @staticmethod
    def _session_for_time(value: datetime | None) -> str:
        if value is None:
            return "UNKNOWN"
        return get_gold_market_session(value)

    @staticmethod
    def _summary_for(direction: NewsDirection, bias: TradeBias, risk: RiskLevel, title: str) -> str:
        return f"{title[:140]}: rules-based XAUUSD impact is {direction.value}/{bias.value} with {risk.value} risk."

    @staticmethod
    def _event_prompt_addition(event_type: str) -> str:
        additions = {
            EventType.CPI.value: "For CPI, compare actual vs forecast when available. Higher-than-expected CPI is often gold-negative through USD/yields.",
            EventType.FOMC_RATE_DECISION.value: "For FOMC, classify tone as hawkish, dovish, neutral, or mixed; press conferences can reverse first reactions.",
            EventType.FOMC_MINUTES.value: "For FOMC minutes, focus on tone, rate path, inflation, employment, and balance sheet language.",
            EventType.NFP.value: "For NFP, consider payrolls, unemployment, and wage growth. Strong labor data can pressure gold through USD/yields.",
            EventType.FED_SPEECH.value: "For Fed speeches, classify tone and focus on rates, inflation, labor market, and balance sheet language.",
            EventType.WAR_ESCALATION.value: "For war escalation, determine whether geopolitical risk or safe-haven demand is increasing.",
        }
        return additions.get(str(event_type).upper(), "")
