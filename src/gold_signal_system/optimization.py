from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import product
from typing import Any


@dataclass(slots=True)
class StrategyParameterProfile:
    id: int
    name: str
    instrument: str
    timeframe: str
    parameters: dict[str, Any]
    is_active: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    activated_at: datetime | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "parameters": self.parameters,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
        }


class ThresholdOptimizationService:
    def __init__(self, walk_forward_service, storage=None) -> None:
        self.walk_forward_service = walk_forward_service
        self.storage = storage
        self.profiles: list[StrategyParameterProfile] = [
            StrategyParameterProfile(
                id=1,
                name="default",
                instrument="XAUUSD",
                timeframe="5m",
                parameters={
                    "minimum_final_confidence": 0.55,
                    "minimum_risk_reward": 1.5,
                    "max_spread": 0.40,
                    "atr_sl_multiplier": 1.6,
                    "atr_tp_multiplier": 2.0,
                },
                is_active=True,
                activated_at=datetime.now(tz=UTC),
            )
        ]
        self.runs: list[dict[str, Any]] = []
        self.candidates: dict[int, list[dict[str, Any]]] = {}
        self.rollback_stack: list[int] = []
        self.reload_from_storage()

    def reload_from_storage(self) -> dict[str, Any]:
        if self.storage is None:
            return {"profiles": len(self.profiles), "runs": len(self.runs)}

        try:
            profiles_payload = self.storage.list_optimization_profiles()
        except Exception:
            return {"profiles": len(self.profiles), "runs": len(self.runs), "status": "STORAGE_SCHEMA_PENDING"}
        if not profiles_payload.get("items"):
            try:
                self.storage.save_optimization_profile(self.profiles[0].model_dump(), change_reason="default_profile_created")
                profiles_payload = self.storage.list_optimization_profiles()
            except Exception:
                profiles_payload = {"items": []}

        loaded_profiles: list[StrategyParameterProfile] = []
        for item in profiles_payload.get("items", []):
            try:
                loaded_profiles.append(
                    StrategyParameterProfile(
                        id=int(item.get("id") or item.get("profile_id")),
                        name=str(item.get("name") or "profile"),
                        instrument=str(item.get("instrument") or "XAUUSD"),
                        timeframe=str(item.get("timeframe") or "5m"),
                        parameters=dict(item.get("parameters") or {}),
                        is_active=bool(item.get("is_active")),
                        created_at=self._parse_dt(item.get("created_at")) or datetime.now(tz=UTC),
                        activated_at=self._parse_dt(item.get("activated_at")),
                    )
                )
            except Exception:
                continue
        if loaded_profiles:
            self.profiles = loaded_profiles

        try:
            runs_payload = self.storage.list_optimization_runs()
        except Exception:
            runs_payload = {"items": []}
        self.runs = list(runs_payload.get("items", []))
        self.candidates = {}
        for run in self.runs:
            key = int(run.get("id") or 0)
            if key:
                self.candidates[key] = list(self.storage.get_optimization_candidates(run.get("run_id") or key).get("items", []))
        return {"profiles": len(self.profiles), "runs": len(self.runs)}

    def active_profile(self) -> dict[str, Any]:
        active = next((profile for profile in self.profiles if profile.is_active), self.profiles[0])
        return active.model_dump()

    def generate_candidates(self, search_space: dict[str, list[Any]]) -> list[dict[str, Any]]:
        keys = list(search_space.keys())
        values = [search_space[key] for key in keys]
        return [dict(zip(keys, combo)) for combo in product(*values)]

    def score_candidate(self, metrics: dict[str, Any]) -> tuple[float, str | None]:
        trade_count = float(metrics.get("total_signals", metrics.get("trades", 0)) or 0)
        win_rate = float(metrics.get("win_rate", 0.0) or 0.0)
        profit_factor = float(metrics.get("profit_factor", 0.0) or 0.0)
        drawdown = float(metrics.get("max_drawdown", 0.0) or 0.0)
        expectancy = float(metrics.get("average_rr", metrics.get("expectancy", 0.0)) or 0.0)
        stability = 1.0 / (1.0 + drawdown)
        score = min(profit_factor, 3.0) * 25.0 + win_rate * 30.0 + expectancy * 15.0 + stability * 15.0
        rejected = None
        if trade_count < 5:
            score -= 25.0
            rejected = "Low trade count."
        if drawdown > 10:
            score -= 20.0
            rejected = "Drawdown too high."
        capped = max(min(score, 100.0), 0.0)
        if rejected == "Low trade count.":
            capped = min(capped, 74.0)
        return round(capped, 4), rejected

    def start(self, candles: list[dict], search_space: dict[str, list[Any]] | None = None) -> dict[str, Any]:
        search_space = search_space or {
            "minimum_final_confidence": [0.55, 0.60],
            "minimum_risk_reward": [1.5, 2.0],
            "max_spread": [0.35, 0.40],
        }
        run_id = len(self.runs) + 1
        durable_run_id = f"OPT-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{run_id:03d}"
        candidates = []
        split = self._split_candles(candles)
        for idx, params in enumerate(self.generate_candidates(search_space), start=1):
            train = self.walk_forward_service.run(split["train"], name=f"optimization_{run_id}_{idx}_train")
            validation = self.walk_forward_service.run(split["validation"], name=f"optimization_{run_id}_{idx}_validation")
            test = self.walk_forward_service.run(split["test"], name=f"optimization_{run_id}_{idx}_unseen")
            score, rejected = self.score_candidate(validation["summary"])
            divergence_warning = self._divergence_warning(validation["summary"], test["summary"])
            profile = StrategyParameterProfile(
                id=len(self.profiles) + 1,
                name=f"candidate_{run_id}_{idx}_v1",
                instrument="XAUUSD",
                timeframe="5m",
                parameters={**self.active_profile()["parameters"], **params},
            )
            self.profiles.append(profile)
            if self.storage is not None:
                self.storage.save_optimization_profile(profile.model_dump(), source_run_id=durable_run_id, change_reason="optimization_candidate")
            candidates.append(
                {
                    "id": idx,
                    "profile_id": profile.id,
                    "version": 1,
                    "parameters": profile.parameters,
                    "metrics": validation["summary"],
                    "training_score": train["summary"],
                    "validation_score": validation["summary"],
                    "unseen_test_score": test["summary"],
                    "score": score,
                    "rank": 0,
                    "rejected_reason": rejected or divergence_warning,
                    "selection_reason": "Best validation score with unseen-test divergence check.",
                }
            )

        candidates.sort(key=lambda item: item["score"], reverse=True)
        for rank, candidate in enumerate(candidates, start=1):
            candidate["rank"] = rank
        best = candidates[0] if candidates else None
        run = {
            "id": run_id,
            "run_id": durable_run_id,
            "name": f"optimization_{run_id}",
            "instrument": "XAUUSD",
            "timeframe": "5m",
            "search_space": search_space,
            "started_at": datetime.now(tz=UTC).isoformat(),
            "completed_at": datetime.now(tz=UTC).isoformat(),
            "status": "COMPLETED",
            "best_profile_id": best["profile_id"] if best else None,
            "summary": {"candidate_count": len(candidates), "best": best},
        }
        self.runs.append(run)
        self.candidates[run_id] = candidates
        if self.storage is not None:
            self.storage.save_optimization_run(run, candidates)
        return run

    def activate(self, profile_id: int) -> dict[str, Any]:
        target = next((profile for profile in self.profiles if profile.id == profile_id), None)
        if target is None:
            self.reload_from_storage()
            target = next((profile for profile in self.profiles if profile.id == profile_id), None)
        if target is None:
            return {"status": "NOT_FOUND", "profile_id": profile_id}
        current = next((profile for profile in self.profiles if profile.is_active), None)
        if current is not None:
            self.rollback_stack.append(current.id)
        for profile in self.profiles:
            profile.is_active = False
        target.is_active = True
        target.activated_at = datetime.now(tz=UTC)
        if self.storage is not None:
            self.storage.set_active_optimization_profile(profile_id, reason="manual_activation")
        return {"status": "OK", "active_profile": target.model_dump()}

    def rollback(self) -> dict[str, Any]:
        if not self.rollback_stack:
            if self.storage is not None:
                profiles = [item for item in self.storage.list_optimization_profiles().get("items", []) if not item.get("is_active")]
                if profiles:
                    self.rollback_stack.append(int(profiles[-1].get("profile_id") or profiles[-1].get("id")))
            if not self.rollback_stack:
                return {"status": "NO_ROLLBACK_AVAILABLE"}
        profile_id = self.rollback_stack.pop()
        target = next((profile for profile in self.profiles if profile.id == profile_id), None)
        if target is None:
            return {"status": "NOT_FOUND", "profile_id": profile_id}
        for profile in self.profiles:
            profile.is_active = False
        target.is_active = True
        target.activated_at = datetime.now(tz=UTC)
        if self.storage is not None:
            current = next((profile for profile in self.profiles if profile.is_active and profile.id != profile_id), None)
            self.storage.save_optimization_rollback(current.id if current else None, profile_id, reason="rollback")
            self.storage.set_active_optimization_profile(profile_id, reason="rollback")
        return {"status": "OK", "active_profile": target.model_dump()}

    def _split_candles(self, candles: list[dict]) -> dict[str, list[dict]]:
        if len(candles) < 90:
            return {"train": candles, "validation": candles, "test": candles}
        one = max(len(candles) // 3, 1)
        return {
            "train": candles[:one],
            "validation": candles[one : one * 2],
            "test": candles[one * 2 :],
        }

    def _divergence_warning(self, validation: dict[str, Any], test: dict[str, Any]) -> str | None:
        val_pf = float(validation.get("profit_factor", 0.0) or 0.0)
        test_pf = float(test.get("profit_factor", 0.0) or 0.0)
        if val_pf > 0 and test_pf < val_pf * 0.5:
            return "Validation/test divergence suggests overfit risk."
        return None

    def _parse_dt(self, value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None
