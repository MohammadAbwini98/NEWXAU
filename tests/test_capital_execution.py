from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
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
from gold_signal_system.capital_execution import CapitalExecutionClient, CapitalExecutionError, CapitalExecutionService
from gold_signal_system.config import RuntimeConfig
from gold_signal_system.contracts import EntryType, FinalRecommendation, RecommendationStatus, SignalDirection
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.storage import InMemoryStorage


def executable_recommendation() -> FinalRecommendation:
    return FinalRecommendation(
        instrument="XAUUSD",
        timeframe="5m",
        signal_time=datetime.now(tz=UTC),
        signal=SignalDirection.BUY,
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
        model_consensus="BULLISH",
        indicator_bias="BULLISH",
        risk_status="PASSED",
        reasons=["test executable signal"],
        expiry_time=datetime.now(tz=UTC) + timedelta(minutes=20),
    )


def executable_recommendation_for_session(session: str) -> FinalRecommendation:
    recommendation = executable_recommendation()
    recommendation.indicator_summary = {"session": session}
    return recommendation


def blocked_by_risk_recommendation() -> FinalRecommendation:
    recommendation = executable_recommendation()
    recommendation.status = RecommendationStatus.BLOCKED_BY_RISK
    recommendation.risk_status = "BLOCKED"
    recommendation.risk_level = "BLOCKED"
    recommendation.blocked_reasons = ["Risk gate blocked the setup."]
    return recommendation


def retest_recommendation() -> FinalRecommendation:
    recommendation = executable_recommendation()
    recommendation.entry_type = EntryType.RETEST
    recommendation.entry_price = 2350.0
    recommendation.current_price = 2345.0
    recommendation.stop_loss = 2342.0
    recommendation.take_profit_1 = 2356.0
    return recommendation


class FakeExecutionClient:
    def __init__(self, demo: bool = True, positions: list[dict] | None = None) -> None:
        self.demo = demo
        self.positions = positions or []
        self.requests: list[dict] = []
        self.selection_calls: list[dict] = []
        self.select_count = 0
        self.invalidate_count = 0
        self.selected_account = {
            "accountId": "ACC-NEWXAU",
            "accountName": "NEWXAU",
            "balance": {"balance": 10000, "available": 9700, "profitLoss": 12.5},
        }

    def is_demo_environment(self) -> bool:
        return self.demo

    def select_account(self, account_name: str, *, force: bool = False) -> dict:
        if account_name != "NEWXAU":
            raise AssertionError("unexpected account")
        self.selection_calls.append({"account_name": account_name, "force": force})
        self.select_count += 1
        return self.selected_account

    def list_positions(self) -> list[dict]:
        return self.positions

    def create_market_position(self, request_payload: dict) -> dict:
        self.requests.append(request_payload)
        return {"dealReference": "DREF-1", "status": "SUBMITTED"}

    def invalidate_session(self) -> None:
        self.invalidate_count += 1

    def confirm(self, deal_reference: str) -> dict:
        return {"dealReference": deal_reference, "dealId": "DEAL-1", "transactionId": "TX-1", "dealStatus": "ACCEPTED"}

    @staticmethod
    def _account_name(account: dict) -> str | None:
        return account.get("accountName")

    @staticmethod
    def _account_id(account: dict) -> str | None:
        return account.get("accountId")


class FakeHttpResponse:
    content = b"{}"
    status_code = 200
    text = "{}"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"dealReference": "DREF-HTTP"}


class FakeHttpSession:
    def __init__(self) -> None:
        self.posts: list[dict] = []

    def request(self, method: str, url: str, **kwargs: dict) -> FakeHttpResponse:
        if method == "POST":
            self.posts.append({"url": url, "json": kwargs.get("json"), "timeout": kwargs.get("timeout")})
        return FakeHttpResponse()

    def post(self, url: str, json: dict, timeout: int) -> FakeHttpResponse:
        self.posts.append({"url": url, "json": json, "timeout": timeout})
        return FakeHttpResponse()


class CapitalExecutionTests(unittest.TestCase):
    def test_capital_client_posts_market_position_to_documented_positions_endpoint(self) -> None:
        runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)
        client = CapitalExecutionClient(runtime)
        fake_session = FakeHttpSession()
        client._session = fake_session  # type: ignore[assignment]
        client._authenticated = True

        response = client.create_market_position({"epic": "GOLD", "direction": "BUY", "size": 0.01})

        self.assertEqual(response["dealReference"], "DREF-HTTP")
        self.assertTrue(fake_session.posts[0]["url"].endswith("/positions"))
        self.assertFalse(fake_session.posts[0]["url"].endswith("/positions/otc"))

    def test_position_create_retries_once_after_401_reauth_and_account_selection(self) -> None:
        class ReauthClient(FakeExecutionClient):
            def __init__(self) -> None:
                super().__init__()
                self.fail_once = True

            def create_market_position(self, request_payload: dict) -> dict:
                if self.fail_once:
                    self.fail_once = False
                    raise CapitalExecutionError("expired token", status_code=401)
                return super().create_market_position(request_payload)

        storage = InMemoryStorage()
        fake = ReauthClient()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=fake,
        )

        result = service.execute_recommendation(11, executable_recommendation(), latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(fake.invalidate_count, 1)
        self.assertGreaterEqual(fake.select_count, 2)
        self.assertEqual(len(fake.requests), 1)

    def test_execution_disabled_blocks_and_persists_audit_order(self) -> None:
        storage = InMemoryStorage()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=False),
            storage,
            client=FakeExecutionClient(),
        )

        result = service.execute_recommendation(1, executable_recommendation())

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("disabled", result["message"].lower())
        self.assertEqual(storage.list_execution_orders()["total"], 1)
        self.assertEqual(storage.list_execution_orders()["items"][0]["status"], "BLOCKED")

    def test_demo_only_blocks_live_api_base(self) -> None:
        storage = InMemoryStorage()
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capital_execution_demo_only=True,
            ),
            storage,
            client=FakeExecutionClient(demo=False),
        )

        result = service.execute_recommendation(1, executable_recommendation())

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("demo-only", result["message"])

    def test_recommended_signal_submits_market_order_and_confirms(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capital_execution_account_name="NEWXAU",
                capital_execution_default_size=0.03,
                capital_execution_max_size=0.10,
                capitalcom_epic="XAUUSD",
            ),
            storage,
            client=fake,
        )

        result = service.execute_recommendation(7, executable_recommendation(), latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(fake.requests[0]["epic"], "XAUUSD")
        self.assertEqual(fake.requests[0]["direction"], "BUY")
        self.assertEqual(fake.requests[0]["size"], 0.03)
        self.assertEqual(fake.requests[0]["stopLevel"], 2347.0)
        self.assertEqual(fake.requests[0]["profitLevel"], 2356.0)
        self.assertEqual(storage.get_execution_order_by_signal(7)["deal_id"], "DEAL-1")
        self.assertEqual(storage.get_execution_order_by_signal(7)["transaction_id"], "TX-1")

    def test_market_order_forces_account_selection_immediately_before_submission(self) -> None:
        class GuardedClient(FakeExecutionClient):
            def __init__(self) -> None:
                super().__init__()
                self.force_generation = 0
                self.last_forced_generation_at_submit = 0

            def select_account(self, account_name: str, *, force: bool = False) -> dict:
                account = super().select_account(account_name, force=force)
                if force:
                    self.force_generation += 1
                return account

            def list_positions(self) -> list[dict]:
                self.last_forced_generation_at_submit = self.force_generation
                return []

            def create_market_position(self, request_payload: dict) -> dict:
                if self.force_generation <= self.last_forced_generation_at_submit:
                    raise AssertionError("market position submitted without a fresh forced account selection")
                return super().create_market_position(request_payload)

        storage = InMemoryStorage()
        fake = GuardedClient()
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
        )

        result = service.execute_recommendation(17, executable_recommendation(), latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(fake.requests[0]["epic"], "XAUUSD")
        self.assertGreaterEqual(len([call for call in fake.selection_calls if call["force"]]), 2)

    def test_broker_noop_account_selection_does_not_block_execution(self) -> None:
        class NoopSelectionClient(FakeExecutionClient):
            def select_account(self, account_name: str, *, force: bool = False) -> dict:
                if force:
                    raise CapitalExecutionError(
                        'Capital.com select account failed with HTTP 400: {"errorCode":"error.not-different.accountId"}',
                        status_code=400,
                        response_body='{"errorCode":"error.not-different.accountId"}',
                    )
                return super().select_account(account_name, force=force)

        storage = InMemoryStorage()
        fake = NoopSelectionClient()
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
        )

        result = service.execute_recommendation(18, executable_recommendation(), latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(len(fake.requests), 1)

    def test_duplicate_signal_is_not_submitted_twice(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capitalcom_epic="XAUUSD",
                capital_execution_max_open_positions=1,
            ),
            storage,
            client=fake,
        )

        first = service.execute_recommendation(3, executable_recommendation())
        second = service.execute_recommendation(3, executable_recommendation())

        self.assertEqual(first["status"], "CONFIRMED")
        self.assertEqual(second["status"], "DUPLICATE")
        self.assertEqual(len(fake.requests), 1)

    def test_open_position_limit_blocks_new_order(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient(positions=[{"market": {"epic": "XAUUSD"}, "position": {"status": "OPEN"}}])
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capitalcom_epic="XAUUSD",
                capital_execution_max_open_positions=1,
            ),
            storage,
            client=fake,
        )

        result = service.execute_recommendation(4, executable_recommendation())

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("Open position limit", result["message"])
        self.assertEqual(len(fake.requests), 0)

    def test_explicitly_allowed_blocked_by_risk_signal_can_execute(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capital_execution_allowed_statuses=("RECOMMENDED", "WEAK_RECOMMENDATION", "BLOCKED_BY_RISK"),
                capital_execution_min_confidence=0.56,
                capitalcom_epic="XAUUSD",
            ),
            storage,
            client=fake,
        )

        result = service.execute_recommendation(
            6,
            blocked_by_risk_recommendation(),
            latest_price_state={"price": 2350.05},
        )

        self.assertEqual(result["status"], "CONFIRMED")
        self.assertEqual(len(fake.requests), 1)

    def test_other_risk_blocked_statuses_still_require_passed_risk(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        recommendation = blocked_by_risk_recommendation()
        recommendation.status = RecommendationStatus.BLOCKED_BY_LOW_RR
        service = CapitalExecutionService(
            RuntimeConfig(
                data_provider="synthetic",
                postgres_dsn=None,
                capital_execution_enabled=True,
                capital_execution_allowed_statuses=("RECOMMENDED", "BLOCKED_BY_LOW_RR"),
                capitalcom_epic="XAUUSD",
            ),
            storage,
            client=fake,
        )

        result = service.execute_recommendation(8, recommendation, latest_price_state={"price": 2350.05})

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("risk status", result["message"])
        self.assertEqual(len(fake.requests), 0)

    def test_execution_orders_can_be_filtered_to_executed_only_with_pagination(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=fake,
        )
        service.execute_recommendation(1, executable_recommendation(), latest_price_state={"price": 2350.05})
        disabled = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=False, capitalcom_epic="XAUUSD"),
            storage,
            client=fake,
        )
        disabled.execute_recommendation(2, executable_recommendation(), latest_price_state={"price": 2350.05})

        result = storage.list_execution_orders(page=1, page_size=1, direction="BUY", executed_only=True)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 1)
        self.assertEqual(result["items"][0]["status"], "CONFIRMED")

    def test_execution_orders_can_be_filtered_by_market_session(self) -> None:
        storage = InMemoryStorage()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=FakeExecutionClient(),
        )
        overlap = executable_recommendation_for_session("US_OVERLAP")
        asia = executable_recommendation_for_session("ASIA_LOW")
        overlap_id = storage.save_recommendation(overlap)
        asia_id = storage.save_recommendation(asia)
        service.execute_recommendation(overlap_id, overlap, latest_price_state={"price": 2350.05})
        service.execute_recommendation(asia_id, asia, latest_price_state={"price": 2350.05})

        result = storage.list_execution_orders(market_session="US_OVERLAP", executed_only=True)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["signal_id"], overlap_id)
        self.assertEqual(result["items"][0]["market_session"], "US_OVERLAP")
        self.assertEqual(result["statistics"]["total"], 1)
        self.assertEqual(result["statistics"]["by_session"]["US_OVERLAP"], 1)

    def test_execution_orders_can_be_filtered_by_requested_time_range(self) -> None:
        storage = InMemoryStorage()
        old_time = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
        new_time = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
        storage.create_execution_order(
            {
                "signal_id": 41,
                "idempotency_key": "capital-signal-41",
                "instrument": "XAUUSD",
                "epic": "GOLD",
                "environment": "demo",
                "direction": "BUY",
                "status": "CONFIRMED",
                "requested_at": old_time.isoformat(),
            }
        )
        storage.create_execution_order(
            {
                "signal_id": 42,
                "idempotency_key": "capital-signal-42",
                "instrument": "XAUUSD",
                "epic": "GOLD",
                "environment": "demo",
                "direction": "SELL",
                "status": "CONFIRMED",
                "requested_at": new_time.isoformat(),
            }
        )

        result = storage.list_execution_orders(
            from_time=datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
            to_time=datetime(2026, 7, 3, 13, 0, tzinfo=UTC),
            executed_only=True,
        )

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["signal_id"], 42)
        self.assertEqual(result["statistics"]["by_direction"]["SELL"], 1)

    def test_refresh_execution_outcomes_marks_win_from_profit_level(self) -> None:
        storage = InMemoryStorage()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=FakeExecutionClient(),
        )
        service.execute_recommendation(9, executable_recommendation(), latest_price_state={"price": 2350.05})

        result = service.refresh_execution_outcomes({"price": 2356.0})

        order = storage.get_execution_order_by_signal(9)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(order["outcome"], "WIN")
        self.assertEqual(order["outcome_reason"], "TAKE_PROFIT_HIT")

    def test_refresh_execution_outcomes_marks_loss_from_stop_level(self) -> None:
        storage = InMemoryStorage()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=FakeExecutionClient(),
        )
        service.execute_recommendation(10, executable_recommendation(), latest_price_state={"price": 2350.05})

        result = service.refresh_execution_outcomes({"price": 2347.0})

        order = storage.get_execution_order_by_signal(10)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(order["outcome"], "LOSS")
        self.assertEqual(order["outcome_reason"], "STOP_LOSS_HIT")

    def test_api_style_execution_blocks_when_price_payload_has_no_price(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=fake,
        )

        result = service.execute_recommendation(5, executable_recommendation(), latest_price_state={"status": "WAITING_FOR_STREAM"})

        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("No live Capital.com price", result["message"])
        self.assertEqual(len(fake.requests), 0)

    def test_non_market_entry_waits_until_price_is_close_to_planned_entry(self) -> None:
        storage = InMemoryStorage()
        fake = FakeExecutionClient()
        service = CapitalExecutionService(
            RuntimeConfig(data_provider="synthetic", postgres_dsn=None, capital_execution_enabled=True, capitalcom_epic="XAUUSD"),
            storage,
            client=fake,
        )

        first = service.execute_recommendation(12, retest_recommendation(), latest_price_state={"price": 2345.0})

        self.assertEqual(first["status"], "PENDING_ENTRY")
        self.assertIn("waiting", first["message"])
        self.assertEqual(len(fake.requests), 0)

        processed = service.process_pending_entries({"price": 2349.25})

        order = storage.get_execution_order_by_signal(12)
        self.assertEqual(processed["processed"], 1)
        self.assertEqual(order["status"], "CONFIRMED")
        self.assertEqual(len(fake.requests), 1)


class CapitalExecutionApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            capital_execution_enabled=False,
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.execution_service = CapitalExecutionService(runtime, api.system.storage, client=FakeExecutionClient())
        api.latest_price_tick = {"price": 2350.0, "timestamp": datetime.now(tz=UTC).isoformat(), "status": "LIVE"}
        api.latest_price_stream_status = {"status": "WAITING_FOR_STREAM"}

    def tearDown(self) -> None:
        if hasattr(api.system.storage, "close"):
            api.system.storage.close()

    async def test_execute_latest_endpoint_uses_latest_signal_and_records_blocked_order(self) -> None:
        signal_id = api.system.storage.save_recommendation(executable_recommendation())

        result = await api.execute_latest_signal({"source": "test"})

        self.assertEqual(signal_id, 1)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(api.system.storage.list_execution_orders()["total"], 1)

    def test_dashboard_contains_execution_view_and_api_calls(self) -> None:
        dashboard_path = os.path.join(ROOT, "src", "gold_signal_system", "dashboard_static", "index.html")
        with open(dashboard_path, encoding="utf-8") as handle:
            html = handle.read()

        self.assertIn('data-view="execution"', html)
        self.assertIn("/api/execution/status", html)
        self.assertIn("/api/execution/orders", html)
        self.assertIn("/api/execution/execute-latest", html)
        self.assertIn('select("market_session", "Session"', html)
        self.assertIn('params.set("market_session"', html)
        self.assertIn('data-execution-filter="from_time"', html)
        self.assertIn('data-execution-filter="to_time"', html)
        self.assertIn("Filtered Orders", html)
        self.assertIn("formatCountSummary(stats.by_session", html)
        self.assertIn('data-control-direction', html)

    async def test_execution_orders_export_uses_full_dashboard_payload_shape(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            capital_execution_enabled=True,
            capitalcom_epic="XAUUSD",
            capital_execution_account_name="NEWXAU",
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.execution_service = CapitalExecutionService(runtime, api.system.storage, client=FakeExecutionClient())
        recommendation = executable_recommendation()
        signal_id = api.system.storage.save_recommendation(recommendation)
        api.execution_service.execute_recommendation(signal_id, recommendation, latest_price_state={"price": 2350.05})

        response = await api.export_execution_orders()
        payload = json.loads(response.body.decode("utf-8"))

        self.assertEqual(payload["total"], 1)
        item = payload["items"][0]
        self.assertEqual(item["execution_order"]["signal_id"], signal_id)
        self.assertEqual(item["signal_detail"]["id"], signal_id)
        self.assertEqual(item["signal_detail"]["signal"], "BUY")
        self.assertEqual(item["broker_response"]["dealReference"], "DREF-1")
        self.assertEqual(item["broker_confirm"]["dealStatus"], "ACCEPTED")

    async def test_execution_orders_api_accepts_market_session_filter(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            capital_execution_enabled=True,
            capitalcom_epic="XAUUSD",
            capital_execution_account_name="NEWXAU",
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.execution_service = CapitalExecutionService(runtime, api.system.storage, client=FakeExecutionClient())
        ny = executable_recommendation_for_session("NY_ACTIVE")
        london = executable_recommendation_for_session("LONDON_ACTIVE")
        ny_id = api.system.storage.save_recommendation(ny)
        london_id = api.system.storage.save_recommendation(london)
        api.execution_service.execute_recommendation(ny_id, ny, latest_price_state={"price": 2350.05})
        api.execution_service.execute_recommendation(london_id, london, latest_price_state={"price": 2350.05})

        result = await api.get_execution_orders(market_session="NY_ACTIVE", from_time=datetime.now(tz=UTC) - timedelta(minutes=1))
        export_response = await api.export_execution_orders(market_session="NY_ACTIVE", from_time=datetime.now(tz=UTC) - timedelta(minutes=1))
        export_payload = json.loads(export_response.body.decode("utf-8"))

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["signal_id"], ny_id)
        self.assertEqual(result["statistics"]["total"], 1)
        self.assertEqual(result["statistics"]["by_session"]["NY_ACTIVE"], 1)
        self.assertEqual(export_payload["filters"]["market_session"], "NY_ACTIVE")
        self.assertIsNotNone(export_payload["filters"]["from_time"])
        self.assertEqual(export_payload["total"], 1)
        self.assertEqual(export_payload["statistics"]["total"], 1)

    async def test_auto_execution_skips_non_candidate_without_order_noise(self) -> None:
        runtime = RuntimeConfig(
            data_provider="synthetic",
            postgres_dsn=None,
            enable_background_cycle_runner=False,
            enable_live_price_stream=False,
            capital_execution_enabled=True,
            capital_execution_auto_execute=True,
            capital_execution_min_confidence=0.56,
        )
        api.runtime = runtime
        api.system = GoldSignalSystem(runtime=runtime)
        api.execution_service = CapitalExecutionService(runtime, api.system.storage, client=FakeExecutionClient())

        recommendation = executable_recommendation()
        recommendation.confidence = 0.42
        api.system.storage.save_recommendation(recommendation)

        result = await api._auto_execute_if_armed(recommendation, "test_auto")

        self.assertIsNone(result)
        self.assertEqual(api.system.storage.list_execution_orders(executed_only=False)["total"], 0)
