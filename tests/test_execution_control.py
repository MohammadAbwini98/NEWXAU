from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

os.environ["POSTGRES_DSN"] = ""
os.environ["DATA_PROVIDER"] = "synthetic"
os.environ["ENABLE_BACKGROUND_CYCLE_RUNNER"] = "0"
os.environ["ENABLE_LIVE_PRICE_STREAM"] = "0"
os.environ["NEWS_COLLECTION_ENABLED"] = "0"
os.environ["NEWS_AI_ANALYSIS_ENABLED"] = "0"
os.environ["CAPITAL_EXECUTION_ACCOUNT_NAME"] = "NEWXAU"

from gold_signal_system import api
from gold_signal_system.capital_execution import CapitalExecutionService
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.contracts import (
    EntryType,
    ExecutionControlConfig,
    FinalRecommendation,
    ModelPrediction,
    RecommendationStatus,
    SignalDirection,
)
from gold_signal_system.execution_control import ExecutionControlService
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.storage import InMemoryStorage


def vote(model_name: str, signal: SignalDirection) -> ModelPrediction:
    buy = 0.70 if signal == SignalDirection.BUY else 0.15
    sell = 0.70 if signal == SignalDirection.SELL else 0.15
    hold = 0.70 if signal == SignalDirection.HOLD else 0.15
    return ModelPrediction(
        model_name=model_name,
        model_version=f"{model_name.lower()}_test",
        instrument="XAUUSD",
        timeframe="1m",
        prediction_time=datetime.now(tz=UTC),
        signal=signal,
        buy_probability=buy,
        sell_probability=sell,
        hold_probability=hold,
        confidence=max(buy, sell, hold),
        expected_return=0.001,
        expected_range=2.0,
        prediction_horizon_candles=8,
    )


def recommendation(
    signal: SignalDirection = SignalDirection.BUY,
    session: str = "LONDON_ACTIVE",
    model_votes: list[ModelPrediction] | None = None,
) -> FinalRecommendation:
    return FinalRecommendation(
        instrument="XAUUSD",
        timeframe="1m",
        signal_time=datetime.now(tz=UTC),
        signal=signal,
        status=RecommendationStatus.RECOMMENDED,
        confidence=0.82,
        score=84.0,
        entry_type=EntryType.MARKET,
        entry_price=2350.0,
        current_price=2350.1,
        stop_loss=2347.0,
        take_profit_1=2356.0,
        take_profit_2=2360.0,
        take_profit_3=2365.0,
        risk_amount=3.0,
        reward_amount=6.0,
        risk_reward=2.0,
        risk_level="LOW",
        valid_for_minutes=20,
        model_consensus="NORMAL_BUY",
        indicator_bias="BULLISH",
        risk_status="PASSED",
        reasons=["test signal"],
        expiry_time=datetime.now(tz=UTC) + timedelta(minutes=20),
        indicator_summary={"session": session},
        model_votes=model_votes
        or [
            vote("KRONOS", SignalDirection.SELL),
            vote("TCN", SignalDirection.BUY),
            vote("LightGBM", SignalDirection.BUY),
        ],
    )


class FakeExecutionClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def is_demo_environment(self) -> bool:
        return True

    def select_account(self, account_name: str, *, force: bool = False) -> dict:
        return {"accountId": "ACC", "accountName": account_name}

    @staticmethod
    def _account_name(account: dict) -> str | None:
        return account.get("accountName")

    @staticmethod
    def _account_id(account: dict) -> str | None:
        return account.get("accountId")

    def list_positions(self) -> list[dict]:
        return []

    def create_market_position(self, request_payload: dict) -> dict:
        self.requests.append(request_payload)
        return {"dealReference": "DREF-1", "status": "SUBMITTED"}

    def confirm(self, deal_reference: str) -> dict:
        return {"dealReference": deal_reference, "dealId": "DEAL-1", "dealStatus": "ACCEPTED"}


class ExecutionControlServiceTests(unittest.TestCase):
    def test_session_toggle_blocks_and_audits_decision(self) -> None:
        storage = InMemoryStorage()
        service = ExecutionControlService(storage)
        service.save_config({"allowed_sessions": {"NY_ACTIVE": False}})

        decision = service.evaluate(1, recommendation(session="NY_ACTIVE"), source="manual")

        self.assertFalse(decision.allowed)
        self.assertIn("NY_ACTIVE", decision.reason)
        audited = storage.list_execution_control_decisions()
        self.assertEqual(audited["total"], 1)
        self.assertEqual(audited["items"][0]["session_name"], "NY_ACTIVE")

    def test_daily_break_is_always_blocked(self) -> None:
        storage = InMemoryStorage()
        service = ExecutionControlService(storage)
        service.save_config({"allowed_sessions": {"DAILY_BREAK": True}})

        decision = service.evaluate(1, recommendation(session="DAILY_BREAK"), source="manual")

        self.assertFalse(decision.allowed)
        self.assertIn("non-trading session", decision.reason)

    def test_direction_toggle_blocks_and_composes_with_session_toggle(self) -> None:
        storage = InMemoryStorage()
        service = ExecutionControlService(storage)
        service.save_config(
            {
                "allowed_sessions": {
                    "ASIA_LOW": False,
                    "LONDON_ACTIVE": False,
                    "US_OVERLAP": True,
                    "NY_ACTIVE": False,
                },
                "allowed_directions": {"BUY": False, "SELL": True},
            }
        )

        allowed = service.evaluate(1, recommendation(signal=SignalDirection.SELL, session="US_OVERLAP"), record=False)
        blocked_direction = service.evaluate(2, recommendation(signal=SignalDirection.BUY, session="US_OVERLAP"), record=False)
        blocked_session = service.evaluate(3, recommendation(signal=SignalDirection.SELL, session="LONDON_ACTIVE"), record=False)

        self.assertTrue(allowed.allowed)
        self.assertFalse(blocked_direction.allowed)
        self.assertIn("BUY", blocked_direction.reason)
        self.assertFalse(blocked_session.allowed)
        self.assertIn("LONDON_ACTIVE", blocked_session.reason)

    def test_kronos_opposite_same_and_tie_gate(self) -> None:
        storage = InMemoryStorage()
        service = ExecutionControlService(storage)
        service.save_config({"require_ensemble_opposite_or_tie": True})

        opposite = service.evaluate(
            1,
            recommendation(
                model_votes=[
                    vote("KRONOS", SignalDirection.SELL),
                    vote("TCN", SignalDirection.BUY),
                    vote("LightGBM", SignalDirection.BUY),
                ]
            ),
            record=False,
        )
        same = service.evaluate(
            2,
            recommendation(
                model_votes=[
                    vote("KRONOS", SignalDirection.BUY),
                    vote("TCN", SignalDirection.BUY),
                    vote("LightGBM", SignalDirection.SELL),
                ]
            ),
            record=False,
        )
        tied = service.evaluate(
            3,
            recommendation(
                model_votes=[
                    vote("KRONOS", SignalDirection.BUY),
                    vote("TCN", SignalDirection.SELL),
                ]
            ),
            record=False,
        )

        self.assertTrue(opposite.allowed)
        self.assertEqual(opposite.kronos_relation, "OPPOSITE")
        self.assertFalse(same.allowed)
        self.assertEqual(same.kronos_relation, "SAME")
        self.assertTrue(tied.allowed)
        self.assertEqual(tied.kronos_relation, "TIE")

    def test_statistics_include_decisions_executions_and_what_if(self) -> None:
        storage = InMemoryStorage()
        service = ExecutionControlService(storage)
        rec_id = storage.save_recommendation(recommendation(session="LONDON_ACTIVE"))
        service.evaluate(rec_id, recommendation(session="LONDON_ACTIVE"), source="manual")
        storage.create_execution_order(
            {
                "signal_id": rec_id,
                "idempotency_key": "capital-signal-1",
                "instrument": "XAUUSD",
                "epic": "GOLD",
                "environment": "demo",
                "direction": "BUY",
                "status": "CONFIRMED",
                "outcome": "WIN",
            }
        )

        stats = service.statistics()

        self.assertEqual(stats["decision_summary"]["total"], 1)
        self.assertEqual(stats["execution_summary"]["outcomes_by_session"]["LONDON_ACTIVE"]["WIN"], 1)
        self.assertEqual(stats["what_if_current_config"]["sample_size"], 1)


class ExecutionControlIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_get_update_and_stats_endpoints(self) -> None:
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=False)
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.execution_service = CapitalExecutionService(runtime, api.system.storage, client=FakeExecutionClient())

        config = ExecutionControlConfig(allowed_sessions={"ASIA_LOW": False})
        update = await api.update_execution_control(config)
        current = await api.get_execution_control()
        stats = await api.get_execution_control_stats()

        self.assertEqual(update["status"], "OK")
        self.assertFalse(current["config"]["allowed_sessions"]["ASIA_LOW"])
        self.assertTrue(current["config"]["allowed_directions"]["BUY"])
        self.assertTrue(current["config"]["allowed_directions"]["SELL"])
        self.assertIn("decision_summary", stats)

    async def test_capital_execution_is_blocked_by_disabled_direction(self) -> None:
        storage = InMemoryStorage()
        control = ExecutionControlService(storage)
        control.save_config({"allowed_directions": {"BUY": False, "SELL": True}})
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capital_execution_account_name="NEWXAU",
                capitalcom_epic="XAUUSD",
            ),
            storage,
            client=fake,
            execution_control=control,
        )

        result = service.execute_recommendation(8, recommendation(signal=SignalDirection.BUY), latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("BUY", result["message"])
        self.assertEqual(fake.requests, [])

    async def test_capital_execution_is_blocked_by_disabled_session(self) -> None:
        storage = InMemoryStorage()
        control = ExecutionControlService(storage)
        control.save_config({"allowed_sessions": {"LONDON_ACTIVE": False}})
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capital_execution_account_name="NEWXAU",
                capitalcom_epic="XAUUSD",
            ),
            storage,
            client=fake,
            execution_control=control,
        )

        result = service.execute_recommendation(7, recommendation(session="LONDON_ACTIVE"), latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("LONDON_ACTIVE", result["message"])
        self.assertEqual(fake.requests, [])
        self.assertEqual(storage.list_execution_control_decisions()["total"], 1)

    async def test_auto_execution_control_block_is_audited_without_execution_order_noise(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            capital_execution_enabled=True,
            capital_execution_auto_execute=True,
            capital_execution_allowed_statuses=("RECOMMENDED",),
            capital_execution_account_name="NEWXAU",
            capitalcom_epic="XAUUSD",
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.execution_control_service = ExecutionControlService(api.system.storage)
        api.execution_control_service.save_config({"allowed_sessions": {"LONDON_ACTIVE": False}})
        api.execution_service = CapitalExecutionService(
            runtime,
            api.system.storage,
            client=FakeExecutionClient(),
            execution_control=api.execution_control_service,
        )
        rec = recommendation(session="LONDON_ACTIVE")
        api.system.storage.save_recommendation(rec)

        result = await api._auto_execute_if_armed(rec, "background_cycle")

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "BLOCKED_BY_CONTROL_UNIT")
        self.assertEqual(api.system.storage.list_execution_orders(executed_only=False)["total"], 0)
        self.assertEqual(api.system.storage.list_execution_control_decisions()["total"], 1)


if __name__ == "__main__":
    unittest.main()
