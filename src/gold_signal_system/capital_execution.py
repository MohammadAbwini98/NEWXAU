from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
import math
import time
from typing import Any
from urllib.parse import quote

import requests

from .config import CAPITAL_DEMO_BASE_URL, RuntimeConfig
from .contracts import FinalRecommendation


class CapitalExecutionError(RuntimeError):
    """Raised when Capital.com execution cannot complete safely."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


def _is_noop_account_selection_error(exc: CapitalExecutionError | Exception | None) -> bool:
    if not isinstance(exc, CapitalExecutionError):
        return False
    payload = f"{exc} {exc.response_body or ''}".lower()
    return "error.not-different.accountid" in payload or "not-different.accountid" in payload


@dataclass(slots=True)
class CapitalExecutionClient:
    runtime: RuntimeConfig
    _session: requests.Session = field(init=False, repr=False)
    _authenticated: bool = field(default=False, init=False, repr=False)
    _active_account: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _selected_account_name: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-CAP-API-KEY": self.runtime.capitalcom_api_key or "",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _normalized_api_base(self) -> str:
        base = (self.runtime.capitalcom_api_base or CAPITAL_DEMO_BASE_URL).rstrip("/")
        if base.endswith("/api/v1"):
            return base
        return f"{base}/api/v1"

    def _build_url(self, path: str) -> str:
        return f"{self._normalized_api_base()}{path}"

    def is_demo_environment(self) -> bool:
        base = self._normalized_api_base().lower()
        return "demo-api-capital" in base or "demo" in base

    def authenticate(self) -> None:
        if self._authenticated:
            return
        if not self.runtime.capitalcom_api_key or not self.runtime.capitalcom_identifier or not self.runtime.capitalcom_password:
            raise CapitalExecutionError("Capital.com credentials are missing.")
        payload = {
            "identifier": self.runtime.capitalcom_identifier,
            "password": self.runtime.capitalcom_password,
            "encryptedPassword": self.runtime.capitalcom_use_encrypted_password,
        }
        response = self._session.post(self._build_url("/session"), json=payload, timeout=10)
        response.raise_for_status()
        cst = response.headers.get("CST")
        token = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not token:
            raise CapitalExecutionError("Capital.com auth response did not include CST/X-SECURITY-TOKEN.")
        self._session.headers["CST"] = cst
        self._session.headers["X-SECURITY-TOKEN"] = token
        self._authenticated = True

    def invalidate_session(self) -> None:
        self._authenticated = False
        self._active_account = None
        self._session.headers.pop("CST", None)
        self._session.headers.pop("X-SECURITY-TOKEN", None)

    def _request_authenticated(
        self,
        method: str,
        path: str,
        *,
        action: str,
        retry_on_401: bool = True,
        **kwargs: Any,
    ) -> requests.Response:
        self.authenticate()
        response = self._session.request(method, self._build_url(path), **kwargs)
        if response.status_code != 401 or not retry_on_401:
            self._raise_for_status(response, action)
            return response

        account_name = self._selected_account_name
        self.invalidate_session()
        self.authenticate()
        if account_name and path != "/accounts" and not (method.upper() == "PUT" and path == "/session"):
            self.select_account(account_name)
        response = self._session.request(method, self._build_url(path), **kwargs)
        self._raise_for_status(response, f"{action} after re-authentication")
        return response

    def list_accounts(self) -> list[dict[str, Any]]:
        response = self._request_authenticated("GET", "/accounts", action="list accounts", timeout=10)
        data = response.json() if response.content else {}
        accounts = data.get("accounts") or data.get("clientAccounts") or data.get("items") or data
        return list(accounts) if isinstance(accounts, list) else []

    def select_account(self, account_name: str, *, force: bool = False) -> dict[str, Any]:
        if not force and self._active_account and self._account_matches(self._active_account, account_name):
            return self._active_account
        accounts = self.list_accounts()
        account = next((item for item in accounts if self._account_matches(item, account_name)), None)
        if not account:
            names = [self._account_name(item) or self._account_id(item) for item in accounts]
            raise CapitalExecutionError(f"Capital.com demo account '{account_name}' was not found. Available accounts: {names}")
        account_id = self._account_id(account)
        if account_id:
            try:
                self._request_authenticated("PUT", "/session", action="select account", json={"accountId": account_id}, timeout=10)
            except CapitalExecutionError as exc:
                if not _is_noop_account_selection_error(exc):
                    raise
        self._active_account = account
        self._selected_account_name = account_name
        return account

    def list_positions(self) -> list[dict[str, Any]]:
        response = self._request_authenticated("GET", "/positions", action="list positions", timeout=10)
        data = response.json() if response.content else {}
        positions = data.get("positions") or data.get("items") or data
        return list(positions) if isinstance(positions, list) else []

    def create_market_position(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request_authenticated(
            "POST",
            "/positions",
            action="create position",
            json=request_payload,
            timeout=10,
        )
        return response.json() if response.content else {}

    def confirm(self, deal_reference: str) -> dict[str, Any]:
        response = self._request_authenticated(
            "GET",
            f"/confirms/{quote(deal_reference, safe='')}",
            action="confirm position",
            timeout=10,
        )
        return response.json() if response.content else {}

    @staticmethod
    def _raise_for_status(response: requests.Response, action: str) -> None:
        if response.status_code < 400:
            return
        body = response.text[:1000] if response.text else ""
        message = f"Capital.com {action} failed with HTTP {response.status_code}"
        if body:
            message = f"{message}: {body}"
        raise CapitalExecutionError(message, status_code=response.status_code, response_body=body)

    @staticmethod
    def _account_id(account: dict[str, Any]) -> str | None:
        value = account.get("accountId") or account.get("id") or account.get("account_id")
        return str(value) if value is not None else None

    @staticmethod
    def _account_name(account: dict[str, Any]) -> str | None:
        value = account.get("accountName") or account.get("accountAlias") or account.get("name") or account.get("account_name")
        return str(value) if value is not None else None

    def _account_matches(self, account: dict[str, Any], account_name: str) -> bool:
        expected = account_name.strip().lower()
        candidates = [self._account_name(account), self._account_id(account), account.get("preferredName")]
        return any(str(candidate or "").strip().lower() == expected for candidate in candidates)


@dataclass(slots=True)
class CapitalExecutionService:
    runtime: RuntimeConfig
    storage: Any
    client: CapitalExecutionClient | None = None
    execution_control: Any | None = None
    _last_snapshot_refresh: float = field(default=0.0, init=False, repr=False)
    _snapshot_refresh_interval: float = field(default=60.0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = CapitalExecutionClient(self.runtime)

    def status(self) -> dict[str, Any]:
        snapshot = self.storage.latest_execution_account_snapshot(self.runtime.capital_execution_account_name)
        snapshot = self._maybe_refresh_snapshot(snapshot)
        demo = self.client.is_demo_environment() if self.client else False
        payload = {
            "enabled": self.runtime.capital_execution_enabled,
            "auto_execute": self.runtime.capital_execution_auto_execute,
            "demo_only": self.runtime.capital_execution_demo_only,
            "environment": "demo" if demo else "live",
            "account_name": self.runtime.capital_execution_account_name,
            "epic": self.runtime.capitalcom_epic,
            "default_size": self.runtime.capital_execution_default_size,
            "max_size": self.runtime.capital_execution_max_size,
            "allowed_statuses": list(self.runtime.capital_execution_allowed_statuses),
            "min_confidence": self.runtime.capital_execution_min_confidence,
            "latest_account_snapshot": snapshot,
            "message": self._status_message(demo),
        }
        if self.execution_control is not None:
            with contextlib.suppress(Exception):
                payload["control_unit"] = self.execution_control.get_config().model_dump(mode="json")
        return payload

    def execute_recommendation(
        self,
        signal_id: int,
        recommendation: FinalRecommendation,
        source: str = "manual",
        latest_price_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        idempotency_key = f"capital-signal-{signal_id}"
        duplicate = self.storage.get_execution_order_by_signal(signal_id)
        if duplicate and duplicate.get("status") not in {"BLOCKED", "FAILED", "PENDING_ENTRY"}:
            return {"status": "DUPLICATE", "order": duplicate, "message": "Signal already has an execution order."}

        base_order = self._base_order(signal_id, idempotency_key, recommendation, source)
        block_reason = self._preflight_block_reason(recommendation, latest_price_state, signal_id=signal_id, source=source)
        if block_reason:
            order = self.storage.create_execution_order({**base_order, "status": "BLOCKED", "error_message": block_reason})
            return {"status": "BLOCKED", "order": order, "message": block_reason}

        pending_reason = self._pending_entry_reason(recommendation, latest_price_state)
        if pending_reason:
            order = self.storage.create_execution_order(
                {
                    **base_order,
                    "status": "PENDING_ENTRY",
                    "error_message": pending_reason,
                    "request_json": {**base_order["request_json"], "pending_reason": pending_reason},
                }
            )
            return {"status": "PENDING_ENTRY", "order": order, "message": pending_reason}

        try:
            order = self._submit_market_order(idempotency_key, base_order, recommendation)
            message = (
                order.get("error_message")
                or order.get("broker_reject_reason")
                or order.get("rejection_reason")
                or "Capital.com execution request processed."
            )
            return {"status": order.get("status", "SUBMITTED"), "order": order, "message": message}
        except Exception as exc:
            order = self.storage.create_execution_order({**base_order, "status": "FAILED", "error_message": str(exc)})
            return {"status": "FAILED", "order": order, "message": str(exc)}

    def should_attempt_auto_execution(self, recommendation: FinalRecommendation) -> bool:
        """Return whether the background loop should create an execution attempt.

        Manual execution still records a clear BLOCKED row. The automatic loop uses
        this lighter gate to avoid filling execution history with HOLD, low-confidence,
        expired, or status-disallowed recommendations that were never broker candidates.
        """
        return self._preflight_block_reason(recommendation, None, include_control=False) is None

    def _preflight_block_reason(
        self,
        recommendation: FinalRecommendation,
        latest_price_state: dict[str, Any] | None,
        signal_id: int | None = None,
        source: str = "manual",
        include_control: bool = True,
    ) -> str | None:
        if not self.runtime.capital_execution_enabled:
            return "Capital.com execution is disabled. Set CAPITAL_EXECUTION_ENABLED=1 to allow demo execution."
        if self.runtime.capital_execution_demo_only and self.client and not self.client.is_demo_environment():
            return "Capital.com execution is demo-only, but the configured API base is not the demo endpoint."
        if self.runtime.capital_execution_auto_execute and not self.runtime.capital_execution_enabled:
            return "Auto execution requested but execution is disabled."
        if include_control and self.execution_control is not None:
            decision = self.execution_control.evaluate(signal_id, recommendation, source=source, record=True)
            if not decision.allowed:
                return decision.reason
        if recommendation.signal.value not in {"BUY", "SELL"}:
            return "Only BUY/SELL recommendations can be executed."
        if recommendation.status.value not in self.runtime.capital_execution_allowed_statuses:
            allowed = ", ".join(self.runtime.capital_execution_allowed_statuses) or "(none)"
            return f"Recommendation status {recommendation.status.value} is not allowed for broker execution (allowed: {allowed})."
        min_confidence = self.runtime.capital_execution_min_confidence
        if min_confidence > 0:
            confidence = float(recommendation.confidence or 0.0)
            if confidence < min_confidence:
                return f"Confidence {confidence:.4f} is below execution minimum {min_confidence:.4f}."
        if str(recommendation.risk_status).upper() != "PASSED" and not self._allows_risk_blocked_status(recommendation):
            return "Recommendation risk status did not pass."
        required_prices = [recommendation.entry_price, recommendation.stop_loss, recommendation.take_profit_1]
        if any(value is None for value in required_prices):
            return "Recommendation is missing entry, stop loss, or TP1."
        if recommendation.expiry_time and recommendation.expiry_time < datetime.now(tz=UTC):
            return "Recommendation expired before execution."
        if latest_price_state and str(latest_price_state.get("status") or "").upper() == "STALE_PRICE_DATA":
            return "Latest market state is stale; waiting for live Capital.com price."
        current = self._fresh_price(recommendation, latest_price_state)
        if latest_price_state is not None and current is None:
            return "No live Capital.com price is available for execution."
        if recommendation.entry_price is not None and current is not None and self._is_market_entry(recommendation):
            deviation = abs(float(current) - float(recommendation.entry_price))
            if deviation > self.runtime.capital_execution_max_price_deviation:
                return f"Current price deviated {deviation:.2f} from entry; max allowed is {self.runtime.capital_execution_max_price_deviation:.2f}."
        return None

    def _pending_entry_reason(self, recommendation: FinalRecommendation, latest_price_state: dict[str, Any] | None) -> str | None:
        if self._is_market_entry(recommendation):
            return None
        current = self._fresh_price(recommendation, latest_price_state)
        if current is None or recommendation.entry_price is None:
            return None
        deviation = abs(float(current) - float(recommendation.entry_price))
        if deviation <= self.runtime.capital_execution_max_price_deviation:
            return None
        entry_type = recommendation.entry_type.value if recommendation.entry_type else "PLANNED"
        return (
            f"{entry_type} entry is waiting for live price to reach planned entry. "
            f"Current deviation is {deviation:.2f}; max allowed is {self.runtime.capital_execution_max_price_deviation:.2f}."
        )

    def _allows_risk_blocked_status(self, recommendation: FinalRecommendation) -> bool:
        status = recommendation.status.value
        return status == "BLOCKED_BY_RISK" and status in self.runtime.capital_execution_allowed_statuses

    def _base_order(self, signal_id: int, idempotency_key: str, recommendation: FinalRecommendation, source: str) -> dict[str, Any]:
        return {
            "signal_id": signal_id,
            "idempotency_key": idempotency_key,
            "instrument": recommendation.instrument,
            "epic": self.runtime.capitalcom_epic,
            "environment": "demo" if self.client and self.client.is_demo_environment() else "live",
            "direction": recommendation.signal.value,
            "order_type": "MARKET",
            "status": "CREATED",
            "recommendation_status": recommendation.status.value,
            "entry_price": recommendation.entry_price,
            "current_price": recommendation.current_price,
            "stop_loss": recommendation.stop_loss,
            "take_profit_1": recommendation.take_profit_1,
            "take_profit_2": recommendation.take_profit_2,
            "take_profit_3": recommendation.take_profit_3,
            "request_json": {"source": source, "recommendation": recommendation.model_dump(mode="json")},
        }

    def _order_request(self, recommendation: FinalRecommendation, size: float) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "epic": self.runtime.capitalcom_epic,
            "direction": recommendation.signal.value,
            "size": size,
            "orderType": "MARKET",
            "guaranteedStop": False,
            "forceOpen": self.runtime.capital_execution_force_open,
            "currencyCode": self.runtime.capital_execution_currency_code,
        }
        if recommendation.stop_loss is not None:
            payload["stopLevel"] = round(float(recommendation.stop_loss), 2)
        if recommendation.take_profit_1 is not None:
            payload["profitLevel"] = round(float(recommendation.take_profit_1), 2)
        return payload

    def _submit_market_order(self, idempotency_key: str, base_order: dict[str, Any], recommendation: FinalRecommendation) -> dict[str, Any]:
        account = self._select_execution_account(force=True)
        account_name = self.client._account_name(account) if self.client else self.runtime.capital_execution_account_name
        account_id = self.client._account_id(account) if self.client else None
        self._save_account_snapshot(account)

        open_positions = self._count_open_positions_for_epic()
        if open_positions >= max(int(getattr(self.runtime, "capital_execution_max_open_positions", 1) or 1), 1):
            message = f"Open position limit reached for {self.runtime.capitalcom_epic}."
            return self.storage.create_execution_order(
                {**base_order, "status": "BLOCKED", "account_id": account_id, "account_name": account_name, "error_message": message}
            )

        size = self._position_size()
        request_payload = self._order_request(recommendation, size)
        order = self.storage.create_execution_order(
            {
                **base_order,
                "status": "READY",
                "account_id": account_id,
                "account_name": account_name,
                "size": size,
                "request_json": request_payload,
                "error_message": None,
            }
        )
        response = self._create_market_position_with_reauth(request_payload)
        deal_reference = response.get("dealReference") or response.get("deal_reference")
        submitted_at = datetime.now(tz=UTC).isoformat()
        order = self.storage.update_execution_order(
            idempotency_key,
            {
                "status": "SUBMITTED",
                "submitted_at": submitted_at,
                "deal_reference": deal_reference,
                "transaction_id": self._broker_transaction_id(response),
                "response_json": response,
                "broker_status": response.get("status"),
                "error_message": None,
            },
        ) or order

        if deal_reference:
            confirmation = self._confirm_with_retries(deal_reference)
            broker_status = str(confirmation.get("dealStatus") or confirmation.get("status") or "").upper()
            final_status = "CONFIRMED" if broker_status in {"ACCEPTED", "OPEN", "CONFIRMED", "SUCCESS"} else "REJECTED"
            order = self.storage.update_execution_order(
                idempotency_key,
                {
                    "status": final_status,
                    "confirmed_at": datetime.now(tz=UTC).isoformat(),
                    "deal_id": confirmation.get("dealId") or confirmation.get("deal_id"),
                    "transaction_id": self._broker_transaction_id(confirmation, response),
                    "broker_status": broker_status or None,
                    "rejection_reason": confirmation.get("reason") or confirmation.get("rejectReason"),
                    "confirm_json": confirmation,
                    "error_message": None,
                },
            ) or order
        return order

    def _create_market_position_with_reauth(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        if not self.client:
            return {}
        self._select_execution_account(force=True)
        try:
            return self.client.create_market_position(request_payload)
        except CapitalExecutionError as exc:
            if exc.status_code != 401:
                raise
            self.client.invalidate_session()
            self._select_execution_account(force=True)
            try:
                return self.client.create_market_position(request_payload)
            except CapitalExecutionError as retry_exc:
                raise CapitalExecutionError(
                    f"{retry_exc} Retried once after re-authentication and account selection.",
                    status_code=retry_exc.status_code,
                    response_body=retry_exc.response_body,
                ) from retry_exc

    def _select_execution_account(self, *, force: bool = False) -> dict[str, Any]:
        if not self.client:
            return {}
        account_name = self.runtime.capital_execution_account_name
        try:
            account = self.client.select_account(account_name, force=force)
        except TypeError:
            account = self.client.select_account(account_name)
        except CapitalExecutionError as exc:
            if _is_noop_account_selection_error(exc):
                return self.client._active_account if hasattr(self.client, "_active_account") else {}
            raise
        if account and not self._account_matches_configured_name(account, account_name):
            actual_name = self.client._account_name(account)
            actual_id = self.client._account_id(account)
            raise CapitalExecutionError(
                f"Selected Capital.com account mismatch. Expected '{account_name}', got name='{actual_name}' id='{actual_id}'."
            )
        return account

    def _account_matches_configured_name(self, account: dict[str, Any], account_name: str) -> bool:
        expected = str(account_name or "").strip().lower()
        candidates = [
            self.client._account_name(account) if self.client else None,
            self.client._account_id(account) if self.client else None,
            account.get("preferredName"),
        ]
        return any(str(candidate or "").strip().lower() == expected for candidate in candidates)

    def _position_size(self) -> float:
        min_size = max(self.runtime.capital_execution_min_size, 0.0)
        max_size = max(self.runtime.capital_execution_max_size, min_size)
        raw_size = min(max(self.runtime.capital_execution_default_size, min_size), max_size)
        step = max(self.runtime.capital_execution_size_step, 0.000001)
        stepped = math.floor(raw_size / step) * step
        return round(max(min_size, min(stepped, max_size)), 8)

    def _count_open_positions_for_epic(self) -> int:
        if not self.client:
            return 0
        positions = self.client.list_positions()
        count = 0
        target = self.runtime.capitalcom_epic.upper()
        for item in positions:
            market = item.get("market") or item.get("instrument") or {}
            position = item.get("position") or item
            epic = str(market.get("epic") or item.get("epic") or "").upper()
            status = str(position.get("status") or item.get("status") or "OPEN").upper()
            if epic == target and status not in {"CLOSED", "DELETED", "CANCELLED"}:
                count += 1
        return count

    def _confirm_with_retries(self, deal_reference: str) -> dict[str, Any]:
        attempts = max(self.runtime.capital_execution_confirm_attempts, 1)
        delay = max(self.runtime.capital_execution_confirm_delay_seconds, 0.0)
        last: dict[str, Any] = {}
        for attempt in range(attempts):
            if attempt and delay:
                time.sleep(delay)
            last = self.client.confirm(deal_reference) if self.client else {}
            status = str(last.get("dealStatus") or last.get("status") or "").upper()
            if status:
                return last
        return last

    def _maybe_refresh_snapshot(self, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
        """Populate/refresh the account snapshot from the broker without requiring a trade.

        Best-effort and throttled: the dashboard polls status() frequently, so we only
        hit Capital.com when the persisted snapshot is missing or older than the refresh
        interval, and we never let a broker/network error break the status response.
        """
        if self.client is None:
            return snapshot
        age = self._snapshot_age_seconds(snapshot)
        if age is not None and age < self._snapshot_refresh_interval:
            return snapshot
        now = time.monotonic()
        if now - self._last_snapshot_refresh < self._snapshot_refresh_interval:
            return snapshot
        self._last_snapshot_refresh = now
        if self.refresh_account_snapshot() is not None:
            return self.storage.latest_execution_account_snapshot(self.runtime.capital_execution_account_name)
        return snapshot

    def refresh_account_snapshot(self) -> dict[str, Any] | None:
        """Fetch the configured demo account from Capital.com and persist a snapshot."""
        if self.client is None:
            return None
        try:
            accounts = self.client.list_accounts()
        except Exception:
            return None
        name = self.runtime.capital_execution_account_name
        account = next((item for item in accounts if self.client._account_matches(item, name)), None)
        if not account:
            return None
        self._save_account_snapshot(account)
        return account

    @staticmethod
    def _snapshot_age_seconds(snapshot: dict[str, Any] | None) -> float | None:
        if not snapshot:
            return None
        created = snapshot.get("created_at")
        if created is None:
            return None
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                return None
        if not isinstance(created, datetime):
            return None
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return (datetime.now(tz=UTC) - created).total_seconds()

    def _save_account_snapshot(self, account: dict[str, Any]) -> None:
        if not account:
            return
        balance = account.get("balance") or {}
        self.storage.save_execution_account_snapshot(
            {
                "account_id": CapitalExecutionClient._account_id(account),
                "account_name": CapitalExecutionClient._account_name(account) or self.runtime.capital_execution_account_name,
                "environment": "demo" if self.client and self.client.is_demo_environment() else "live",
                "balance": self._first_number(balance.get("balance"), balance.get("deposit"), account.get("balance")),
                "available": self._first_number(balance.get("available"), balance.get("availableCash"), account.get("available")),
                "profit_loss": self._first_number(balance.get("profitLoss"), balance.get("profit_loss"), account.get("profitLoss")),
                "raw_json": account,
            }
        )

    def _fresh_price(self, recommendation: FinalRecommendation, latest_price_state: dict[str, Any] | None) -> float | None:
        if latest_price_state:
            preferred_keys = ("ask", "price", "mid", "bid") if recommendation.signal.value == "BUY" else ("bid", "price", "mid", "ask")
            for key in preferred_keys:
                value = latest_price_state.get(key)
                if value is not None:
                    return float(value)
            return None
        return float(recommendation.current_price) if recommendation.current_price is not None else None

    @staticmethod
    def _is_market_entry(recommendation: FinalRecommendation) -> bool:
        return recommendation.entry_type is None or recommendation.entry_type.value == "MARKET"

    def _status_message(self, demo: bool) -> str:
        if not self.runtime.capital_execution_enabled:
            return "Execution is disabled. Orders are blocked until CAPITAL_EXECUTION_ENABLED=1."
        if self.runtime.capital_execution_demo_only and not demo:
            return "Execution is blocked because demo-only mode is enabled and API base is not demo."
        if not self.runtime.capital_execution_auto_execute:
            return "Manual demo execution is available. Auto execution is disabled."
        return "Auto demo execution is armed for eligible signals."

    def process_pending_entries(
        self,
        latest_price_state: dict[str, Any] | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        orders = self.storage.list_execution_orders(
            page=1,
            page_size=limit,
            status="PENDING_ENTRY",
            executed_only=False,
        ).get("items", [])
        processed: list[dict[str, Any]] = []
        for order in orders:
            recommendation = self._recommendation_from_order(order)
            if recommendation is None:
                continue
            block_reason = self._preflight_block_reason(recommendation, latest_price_state)
            if block_reason:
                updated = self.storage.update_execution_order(
                    str(order.get("idempotency_key")),
                    {"status": "BLOCKED", "error_message": block_reason},
                )
                if updated:
                    processed.append(updated)
                continue
            pending_reason = self._pending_entry_reason(recommendation, latest_price_state)
            if pending_reason:
                continue
            try:
                submitted = self._submit_market_order(str(order.get("idempotency_key")), {**order, "request_json": order.get("request_json") or {}}, recommendation)
                processed.append(submitted)
            except Exception as exc:
                updated = self.storage.update_execution_order(
                    str(order.get("idempotency_key")),
                    {"status": "FAILED", "error_message": str(exc)},
                )
                if updated:
                    processed.append(updated)
        return {"processed": len(processed), "items": processed}

    def refresh_execution_outcomes(
        self,
        latest_price_state: dict[str, Any] | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        current = self._price_from_state(latest_price_state)
        if current is None:
            return {"updated": 0, "message": "No live price is available for execution outcome refresh."}

        orders = self.storage.list_execution_orders(
            page=1,
            page_size=limit,
            outcome="PENDING",
            executed_only=True,
        ).get("items", [])
        updated: list[dict[str, Any]] = []
        for order in orders:
            outcome, reason = self._execution_outcome_from_price(order, current)
            if outcome is None:
                continue
            saved = self.storage.update_execution_order(
                str(order.get("idempotency_key")),
                {
                    "outcome": outcome,
                    "outcome_reason": reason,
                    "outcome_updated_at": datetime.now(tz=UTC).isoformat(),
                    "broker_status": order.get("broker_status") or "PRICE_LEVEL_HIT",
                },
            )
            if saved:
                updated.append(saved)
        return {"updated": len(updated), "items": updated}

    @staticmethod
    def _price_from_state(state: dict[str, Any] | None) -> float | None:
        if not state:
            return None
        for key in ("price", "mid", "bid", "ask"):
            value = state.get(key)
            if value is not None:
                return float(value)
        return None

    @staticmethod
    def _execution_outcome_from_price(order: dict[str, Any], current: float) -> tuple[str | None, str | None]:
        direction = str(order.get("direction") or "").upper()
        stop_loss = order.get("stop_loss")
        take_profit = order.get("take_profit_1")
        if direction not in {"BUY", "SELL"} or stop_loss is None or take_profit is None:
            return None, None
        sl = float(stop_loss)
        tp = float(take_profit)
        if direction == "BUY":
            if current <= sl:
                return "LOSS", "STOP_LOSS_HIT"
            if current >= tp:
                return "WIN", "TAKE_PROFIT_HIT"
        else:
            if current >= sl:
                return "LOSS", "STOP_LOSS_HIT"
            if current <= tp:
                return "WIN", "TAKE_PROFIT_HIT"
        return None, None

    @staticmethod
    def _broker_transaction_id(*payloads: dict[str, Any]) -> str | None:
        keys = ("transactionId", "transaction_id", "dealId", "deal_id")
        for payload in payloads:
            for key in keys:
                value = payload.get(key)
                if value is not None:
                    return str(value)
            affected = payload.get("affectedDeals")
            if isinstance(affected, list):
                for item in affected:
                    if not isinstance(item, dict):
                        continue
                    for key in keys:
                        value = item.get(key)
                        if value is not None:
                            return str(value)
        return None

    @staticmethod
    def _recommendation_from_order(order: dict[str, Any]) -> FinalRecommendation | None:
        request_json = order.get("request_json") or {}
        recommendation_payload = request_json.get("recommendation") if isinstance(request_json, dict) else None
        if not isinstance(recommendation_payload, dict):
            return None
        try:
            return FinalRecommendation.model_validate(recommendation_payload)
        except Exception:
            return None

    @staticmethod
    def _first_number(*values: Any) -> float | None:
        for value in values:
            try:
                if value is not None:
                    return float(value)
            except Exception:
                continue
        return None
