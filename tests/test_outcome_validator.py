from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.contracts import Candle, EntryType, FinalRecommendation, RecommendationStatus, SignalDirection
from gold_signal_system.outcome_validator import SignalOutcomeValidator


def _rec(direction: SignalDirection = SignalDirection.BUY, entry_type: EntryType = EntryType.LIMIT_PULLBACK) -> FinalRecommendation:
    ts = datetime(2026, 6, 7, 10, 0, tzinfo=UTC)
    return FinalRecommendation(
        instrument="XAUUSD",
        timeframe="5m",
        signal_time=ts,
        signal=direction,
        status=RecommendationStatus.RECOMMENDED,
        confidence=0.8,
        score=82,
        entry_type=entry_type,
        entry_price=100.0,
        current_price=101.0 if direction == SignalDirection.BUY else 99.0,
        stop_loss=98.0 if direction == SignalDirection.BUY else 102.0,
        take_profit_1=102.0 if direction == SignalDirection.BUY else 98.0,
        take_profit_2=104.0 if direction == SignalDirection.BUY else 96.0,
        take_profit_3=106.0 if direction == SignalDirection.BUY else 94.0,
        risk_amount=2.0,
        reward_amount=4.0,
        risk_reward=2.0,
        risk_level="LOW",
        valid_for_minutes=15,
        model_consensus="STRONG_BUY",
        indicator_bias="BULLISH",
        risk_status="PASSED",
        expiry_time=ts + timedelta(minutes=15),
    )


def _candle(ts: datetime, low: float, high: float) -> Candle:
    return Candle(
        instrument="XAUUSD",
        timeframe="5m",
        candle_time=ts,
        open=(low + high) / 2,
        high=high,
        low=low,
        close=(low + high) / 2,
    )


class OutcomeValidatorTests(unittest.TestCase):
    def test_buy_signal_hits_profit_after_entry(self) -> None:
        rec = _rec()
        candles = [
            _candle(rec.signal_time, 100.5, 101.2),
            _candle(rec.signal_time + timedelta(minutes=5), 99.8, 104.3),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "WIN")
        self.assertTrue(result.entry_triggered)
        self.assertEqual(result.realized_rr, 2.0)
        self.assertEqual(result.exit_reason, "TP2_HIT")

    def test_buy_signal_hits_loss_after_entry(self) -> None:
        rec = _rec()
        candles = [
            _candle(rec.signal_time, 100.5, 101.2),
            _candle(rec.signal_time + timedelta(minutes=5), 97.8, 101.0),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "LOSS")
        self.assertTrue(result.entry_triggered)
        self.assertEqual(result.realized_rr, -1.0)
        self.assertEqual(result.exit_reason, "SL_HIT")

    def test_sell_signal_hits_profit_after_entry(self) -> None:
        rec = _rec(SignalDirection.SELL)
        candles = [
            _candle(rec.signal_time, 98.8, 99.5),
            _candle(rec.signal_time + timedelta(minutes=5), 95.8, 100.0),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "WIN")
        self.assertTrue(result.entry_triggered)
        self.assertEqual(result.realized_rr, 2.0)
        self.assertEqual(result.exit_reason, "TP2_HIT")

    def test_sell_signal_hits_loss_after_entry(self) -> None:
        rec = _rec(SignalDirection.SELL)
        candles = [
            _candle(rec.signal_time, 98.8, 99.5),
            _candle(rec.signal_time + timedelta(minutes=5), 99.5, 102.2),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "LOSS")
        self.assertTrue(result.entry_triggered)
        self.assertEqual(result.realized_rr, -1.0)

    def test_limit_signal_expires_out_of_entry_scope(self) -> None:
        rec = _rec()
        candles = [
            _candle(rec.signal_time + timedelta(minutes=5), 101.1, 102.0),
            _candle(rec.signal_time + timedelta(minutes=20), 101.3, 102.4),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "MISSED_ENTRY")
        self.assertFalse(result.entry_triggered)
        self.assertEqual(result.exit_reason, "ENTRY_NOT_TRIGGERED_BEFORE_EXPIRY")

    def test_entry_triggered_signal_expires_without_target_or_stop(self) -> None:
        rec = _rec()
        candles = [
            _candle(rec.signal_time + timedelta(minutes=5), 99.8, 101.0),
            _candle(rec.signal_time + timedelta(minutes=20), 100.2, 101.5),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "EXPIRED")
        self.assertTrue(result.entry_triggered)
        self.assertEqual(result.exit_reason, "EXPIRED")

    def test_tp1_then_reversal_to_stop_is_partial_tp(self) -> None:
        rec = _rec()
        candles = [
            _candle(rec.signal_time + timedelta(minutes=5), 99.8, 102.5),
            _candle(rec.signal_time + timedelta(minutes=10), 97.8, 101.0),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "PARTIAL_TP")
        self.assertEqual(result.exit_reason, "SL_AFTER_TP1")
        self.assertEqual(result.realized_rr, 1.0)

    def test_same_candle_hits_tp_and_sl_uses_conservative_loss(self) -> None:
        rec = _rec()
        candles = [
            _candle(rec.signal_time + timedelta(minutes=5), 97.8, 104.5),
        ]

        result = SignalOutcomeValidator().validate(rec, candles)

        self.assertEqual(result.outcome_status, "LOSS")
        self.assertEqual(result.exit_reason, "SL_HIT_AMBIGUOUS")
        self.assertTrue(result.ambiguous_candle)


if __name__ == "__main__":
    unittest.main()
