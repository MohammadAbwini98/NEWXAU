from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .contracts import FinalRecommendation, RecommendationStatus


@dataclass(slots=True)
class TelegramConfig:
    bot_token: str
    chat_id: str


class LiveControlCenter:
    """Phase 10: controlled live mode with manual confirmation and emergency stop."""

    def __init__(self) -> None:
        self.manual_confirmation_mode = True
        self.emergency_stop_enabled = False
        self.max_trades_per_day = 10
        self.executed_today = 0

    def set_manual_confirmation(self, enabled: bool) -> None:
        self.manual_confirmation_mode = enabled

    def enable_emergency_stop(self) -> None:
        self.emergency_stop_enabled = True

    def disable_emergency_stop(self) -> None:
        self.emergency_stop_enabled = False

    def can_execute(self, recommendation: FinalRecommendation) -> tuple[bool, str]:
        if self.emergency_stop_enabled:
            return False, "Emergency stop enabled"
        if self.executed_today >= self.max_trades_per_day:
            return False, "Daily trade limit reached"
        if recommendation.status not in (
            RecommendationStatus.RECOMMENDED,
            RecommendationStatus.WEAK_RECOMMENDATION,
        ):
            return False, "Recommendation is not executable"
        return True, "OK"

    def process_recommendation(self, recommendation: FinalRecommendation, confirmed: bool = False) -> str:
        allowed, reason = self.can_execute(recommendation)
        if not allowed:
            return f"BLOCKED: {reason}"

        if self.manual_confirmation_mode and not confirmed:
            return "WAITING_MANUAL_CONFIRMATION"

        self.executed_today += 1
        return "EXECUTED"

    def send_telegram_alert(self, config: TelegramConfig, recommendation: FinalRecommendation) -> dict:
        message = {
            "instrument": recommendation.instrument,
            "timeframe": recommendation.timeframe,
            "signal": recommendation.signal.value,
            "status": recommendation.status.value,
            "confidence": recommendation.confidence,
            "entry": recommendation.entry_price,
            "sl": recommendation.stop_loss,
            "tp1": recommendation.take_profit_1,
            "tp2": recommendation.take_profit_2,
            "tp3": recommendation.take_profit_3,
        }
        text = json.dumps(message, ensure_ascii=True)

        url = f"https://api.telegram.org/bot{config.bot_token}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": config.chat_id, "text": text}).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
