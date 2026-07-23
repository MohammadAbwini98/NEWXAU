from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from .config import ModelWeights, RiskLimits, RuntimeConfig
from .contracts import DataQualityReport, FinalRecommendation, MarketContext, RecommendationStatus, SignalDirection
from .data_engine import DataEngine, InMemoryCandleStore
from .dynamic_weights import DynamicModelWeightService, ModelWeightResult
from .health import SystemHealthService
from .indicator_engine import FeatureIndicatorEngine
from .live_control import LiveControlCenter, TelegramConfig
from .market_regime import MarketRegimeDetector
from .model_ensemble import ModelEnsembleEngine
from .multi_timeframe import MultiTimeframeConfirmationService
from .news_filter import EconomicNewsFilter, build_news_provider
from .outcome_validator import FINAL_OUTCOMES, SignalOutcomeValidator
from .performance import ModelPerformanceTracker
from .providers import build_candle_provider
from .recommendation_builder import RecommendationBuilder
from .risk_engine import RiskEngine
from .storage import InMemoryStorage, PostgreSQLStorage, SignalOutcome, SignalSnapshot
from .strategy_brain import StrategyBrain, StrategyThresholdProfile
from .trade_plan_engine import EntrySlTpEngine
from .smc_engine import SMCEngine
from .news_intelligence.repository import NewsIntelligenceRepository
from .news_intelligence.models import StrategyNewsStateModel
from .news_intelligence.service import NewsIntelligenceService
from .news_intelligence.strategy_integration import NewsStateAggregator


@dataclass(slots=True)
class CycleResult:
    recommendation: FinalRecommendation
    data_quality_report: DataQualityReport
    aggregation_counts: dict[str, int]
    processing_timings_ms: dict[str, float]


class GoldSignalSystem:
    """End-to-end implementation across phases 1-10."""

    def __init__(
        self,
        runtime: RuntimeConfig | None = None,
        model_weights: ModelWeights | None = None,
        risk_limits: RiskLimits | None = None,
    ) -> None:
        self.runtime = runtime or RuntimeConfig()
        self.candle_store = InMemoryCandleStore()

        self.storage_backend = "in_memory"
        if self.runtime.postgres_dsn:
            try:
                self.storage = PostgreSQLStorage(self.runtime.postgres_dsn, schema=self.runtime.postgres_schema)
                self.storage_backend = "postgresql"
            except Exception as exc:
                self.storage = InMemoryStorage()
                self.storage.system_settings["storage_warning"] = f"PostgreSQL unavailable, fallback to in-memory: {exc}"
        else:
            self.storage = InMemoryStorage()

        self.candle_provider = build_candle_provider(self.runtime)
        persisted_model_weights = self.storage.get_setting("model_weights.active")
        if model_weights is None and persisted_model_weights:
            weights_payload = persisted_model_weights.get("setting_value_json") or persisted_model_weights.get("setting_value") or {}
            if isinstance(weights_payload, dict):
                model_weights = ModelWeights(weights={str(k): float(v) for k, v in weights_payload.items()})
        self.configured_model_weights = ModelWeights(weights=dict((model_weights or ModelWeights()).weights))

        self.data_engine = DataEngine()
        self.indicator_engine = FeatureIndicatorEngine()
        self.smc_engine = SMCEngine()
        self.model_engine = ModelEnsembleEngine(self.runtime, model_weights)
        self.dynamic_weight_service = DynamicModelWeightService(
            min_weight=self.runtime.model_weight_min,
            max_weight=self.runtime.model_weight_max,
            max_change_per_update=self.runtime.model_weight_max_change_per_update,
            performance_window=self.runtime.model_weight_performance_window,
            min_observations_for_reweight=self.runtime.min_observations_for_reweight,
        )
        persisted_weight_state = self.storage.load_model_weight_state()
        if persisted_weight_state.get("weights"):
            self.model_engine.model_weights = ModelWeights(weights={str(k): float(v) for k, v in persisted_weight_state["weights"].items()})
            self.dynamic_weight_service._last_effective_weights = dict(self.model_engine.model_weights.weights)
            # Persisted version rows use DB column names (weights_json/version_number); the
            # service expects in-process keys (weights/version). Normalize on hydration so
            # _save_profile_version() and rollback() don't KeyError after a restart.
            normalized_versions: list[dict] = []
            for raw_version in persisted_weight_state.get("versions") or []:
                raw_weights = raw_version.get("weights") or raw_version.get("weights_json") or {}
                weights = {str(k): float(v) for k, v in raw_weights.items()}
                version_number = int(
                    raw_version.get("version")
                    or raw_version.get("version_number")
                    or len(normalized_versions) + 1
                )
                normalized_versions.append(
                    {**raw_version, "version": version_number, "weights": weights, "model_weights_json": weights}
                )
            self.dynamic_weight_service.profile_versions = normalized_versions
            if normalized_versions:
                self.dynamic_weight_service.active_profile_version = normalized_versions[-1]["version"]
        self.market_regime_detector = MarketRegimeDetector()
        self.multi_timeframe_service = MultiTimeframeConfirmationService()
        self.news_filter = EconomicNewsFilter(
            provider=build_news_provider(self.runtime.news_provider_mode, self.runtime.news_provider_url),
            block_before_minutes=self.runtime.news_block_before_minutes,
            block_after_minutes=self.runtime.news_block_after_minutes,
            mode=self.runtime.news_provider_mode,
            block_mode=self.runtime.news_block_mode,
        )
        self.threshold_profile = StrategyThresholdProfile(
            profile_id=1,
            version=1,
            name=self.runtime.threshold_profile_name,
            minimum_final_confidence=self.runtime.minimum_final_confidence,
            recommended_score=self.runtime.recommended_score,
            weak_recommendation_score=self.runtime.weak_recommendation_score,
            minimum_risk_reward=self.runtime.minimum_risk_reward,
            adx_threshold=self.runtime.adx_threshold,
            raw={
                "source": "runtime_config",
                "minimum_model_agreement": self.runtime.minimum_model_agreement,
                "atr_minimum": self.runtime.atr_minimum,
                "atr_maximum": self.runtime.atr_maximum,
                "max_spread": RiskLimits().max_spread,
            },
        )
        self.strategy_brain = StrategyBrain(self.threshold_profile)
        self.trade_engine = EntrySlTpEngine()
        persisted_risk_limits = self.storage.get_setting("risk_limits.active")
        if risk_limits is None and persisted_risk_limits:
            risk_payload = persisted_risk_limits.get("setting_value_json") or persisted_risk_limits.get("setting_value") or {}
            if isinstance(risk_payload, dict):
                current_limits = RiskLimits()
                for key, value in risk_payload.items():
                    if hasattr(current_limits, key):
                        setattr(current_limits, key, value)
                risk_limits = current_limits
        self.risk_engine = RiskEngine(risk_limits)
        self.recommendation_builder = RecommendationBuilder()
        self.outcome_validator = SignalOutcomeValidator()
        self.live_control = LiveControlCenter()
        self.health_service = SystemHealthService(self.storage)
        self.performance_tracker = ModelPerformanceTracker(
            min_observations_for_reweight=self.runtime.min_observations_for_reweight
        )
        self.news_repository = NewsIntelligenceRepository(
            dsn=self.runtime.postgres_dsn, schema=self.runtime.postgres_schema
        )
        self.news_aggregator = NewsStateAggregator(repository=self.news_repository, config=self.runtime)
        self.news_intelligence_service = NewsIntelligenceService(
            repository=self.news_repository,
            runtime=self.runtime,
            aggregator=self.news_aggregator,
        )

    def _news_state_for_strategy(self, state: StrategyNewsStateModel | None) -> StrategyNewsStateModel | None:
        if state is None:
            return None
        if self.runtime.news_strategy_weight_enabled:
            return state
        return state.model_copy(update={"active_news_weight": 0.0, "block_trading": False})

    def _news_state_for_risk(self, state: StrategyNewsStateModel | None) -> StrategyNewsStateModel | None:
        if state is None:
            return None
        if self.runtime.news_trade_block_enabled:
            return state
        if self.runtime.news_risk_reduction_enabled and state.reduce_position_size:
            return state.model_copy(update={"block_trading": False})
        return None

    def run_live_cycle(
        self,
        source_timeframe: str = "1m",
        market_context: MarketContext | None = None,
    ) -> CycleResult:
        candles = self.candle_provider.fetch_latest_candles(
            instrument=self.runtime.instrument,
            timeframe=source_timeframe,
            limit=self.runtime.live_candle_lookback,
        )
        return self.run_signal_cycle(
            raw_candles=candles,
            source_timeframe=source_timeframe,
            market_context=market_context,
            data_reference_time=datetime.now(tz=UTC),
            provider_status="AVAILABLE",
        )

    def run_signal_cycle(
        self,
        raw_candles: list[dict[str, Any]],
        source_timeframe: str = "1m",
        market_context: MarketContext | None = None,
        data_reference_time: datetime | None = None,
        provider_status: str = "UNKNOWN",
    ) -> CycleResult:
        cycle_started = perf_counter()
        processing_timings_ms: dict[str, float] = {}
        market_context = market_context or MarketContext()

        stage_started = perf_counter()
        clean_candles, report = self.data_engine.clean_candles(
            raw_candles=raw_candles,
            instrument=self.runtime.instrument,
            timeframe=source_timeframe,
            reference_time=data_reference_time,
            provider_status=provider_status,
            max_missing_ratio=self.runtime.data_quality_max_missing_ratio,
            max_outlier_ratio=self.runtime.data_quality_max_outlier_ratio,
            max_freshness_seconds=(
                self.runtime.data_quality_freshness_multiplier
                * self.data_engine.timeframe_seconds(source_timeframe)
                if data_reference_time is not None
                else None
            ),
            minimum_quality_score=self.runtime.data_quality_min_score,
        )
        if market_context.spread > self.risk_engine.limits.max_spread:
            report.spread_status = "BLOCKED"
            report.blocking_reasons.append(
                f"Spread {market_context.spread:.4f} exceeds {self.risk_engine.limits.max_spread:.4f}."
            )
        elif market_context.spread > self.risk_engine.limits.max_spread * 0.8:
            report.spread_status = "CAUTION"
        else:
            report.spread_status = "OK"
        self.candle_store.upsert_many(clean_candles)
        self.storage.save_candles(clean_candles)
        processing_timings_ms["data_validation"] = round((perf_counter() - stage_started) * 1000.0, 3)

        stage_started = perf_counter()
        aggregation_counts: dict[str, int] = {}
        if source_timeframe == "1m":
            incomplete_total = 0
            for target_tf in ("5m", "15m", "30m", "1h", "4h"):
                all_aggregated = self.data_engine.aggregate_from_1m(clean_candles, target_tf)
                complete_aggregated = self.data_engine.aggregate_from_1m(
                    clean_candles,
                    target_tf,
                    require_complete=True,
                )
                incomplete_count = len(all_aggregated) - len(complete_aggregated)
                incomplete_total += incomplete_count
                aggregation_counts[f"{target_tf}_incomplete"] = incomplete_count
                aggregated = complete_aggregated if self.runtime.enable_data_quality_gate else all_aggregated
                self.candle_store.upsert_many(aggregated)
                self.storage.save_candles(aggregated)
                aggregation_counts[target_tf] = len(aggregated)
            self._top_up_native_timeframes(aggregation_counts)
            if incomplete_total:
                report.aggregation_status = (
                    "FILTERED_INCOMPLETE" if self.runtime.enable_data_quality_gate else "PARTIAL_BUCKETS_PRESENT"
                )
                report.issues.append(f"Incomplete higher-timeframe buckets detected: {incomplete_total}")
            else:
                report.aggregation_status = "COMPLETE"
        else:
            report.aggregation_status = "NOT_APPLICABLE"
        report.blocking_reasons = list(dict.fromkeys(report.blocking_reasons))
        data_quality_blocked = self.runtime.enable_data_quality_gate and bool(report.blocking_reasons)
        report.gate_status = "BLOCKED" if data_quality_blocked else (
            "PASSED" if self.runtime.enable_data_quality_gate else "MONITOR_ONLY"
        )
        processing_timings_ms["aggregation"] = round((perf_counter() - stage_started) * 1000.0, 3)

        stage_started = perf_counter()
        cycle_tf = self.runtime.cycle_timeframe
        candles_for_cycle = self.candle_store.get(self.runtime.instrument, cycle_tf, limit=300)
        if len(candles_for_cycle) < 40:
            # Fallback to source candles for small datasets.
            candles_for_cycle = clean_candles
            cycle_tf = source_timeframe

        candles_by_tf = {
            timeframe: self.candle_store.get(self.runtime.instrument, timeframe, limit=300)
            for timeframe in ("1m", "5m", "15m", "30m", "1h", "4h")
        }

        features = self.indicator_engine.compute_features(candles_for_cycle)
        news_status = "CLEAR" if market_context.minutes_to_high_impact_news is None else "NEWS_WINDOW"
        snapshot = self.indicator_engine.build_indicator_snapshot(
            instrument=self.runtime.instrument,
            timeframe=cycle_tf,
            candles=candles_for_cycle,
            news_status=news_status,
        )
        snapshot.smc = self.smc_engine.build_snapshot(candles_by_tf, datetime.now(tz=UTC), cycle_tf)
        self.storage.save_indicator_snapshot(snapshot)

        market_regime = self.market_regime_detector.detect(snapshot, candles_for_cycle)
        news_risk = self.news_filter.current_risk(snapshot.snapshot_time)
        if news_risk.status == "BLOCKED":
            if news_risk.minutes_to_event is not None:
                market_context.minutes_to_high_impact_news = news_risk.minutes_to_event
            if news_risk.minutes_since_event is not None:
                market_context.minutes_since_high_impact_news = news_risk.minutes_since_event
        elif news_risk.status == "CAUTION":
            market_context.special_volatility_mode = True
        processing_timings_ms["feature_and_context"] = round((perf_counter() - stage_started) * 1000.0, 3)

        stage_started = perf_counter()
        prediction_time = datetime.now(tz=UTC)
        if data_quality_blocked:
            model_votes = self.model_engine.build_abstain_predictions(snapshot, prediction_time=prediction_time)
        else:
            model_votes = self.model_engine.run_models(
                snapshot,
                features,
                prediction_time=prediction_time,
                candles=candles_for_cycle,
            )
        self.storage.save_model_predictions(model_votes)
        processing_timings_ms["model_inference"] = round((perf_counter() - stage_started) * 1000.0, 3)

        stage_started = perf_counter()
        base_weights = dict(self.configured_model_weights.weights)
        if data_quality_blocked:
            current_weights = dict(self.model_engine.model_weights.weights)
            weight_total = sum(current_weights.values()) or 1.0
            dynamic_weight_results = [
                ModelWeightResult(
                    model_name=vote.model_name.lower(),
                    base_weight=float(base_weights.get(vote.model_name.lower(), 0.0)),
                    effective_weight=float(current_weights.get(vote.model_name.lower(), 0.0)) / weight_total,
                    adjustment_reason={"reason": "Data-quality abstention retained existing weights."},
                )
                for vote in model_votes
            ]
        else:
            dynamic_weight_results = self.dynamic_weight_service.calculate(
                base_weights=base_weights,
                predictions=model_votes,
                metrics=self.performance_tracker.metrics(),
                market_regime=market_regime.primary_regime,
                session=snapshot.session_name,
            )
        effective_weights = {item.model_name: item.effective_weight for item in dynamic_weight_results}
        self.model_engine.model_weights = ModelWeights(weights=effective_weights)
        self.storage.save_model_weight_state(
            weights=effective_weights,
            history=[item.model_dump() for item in dynamic_weight_results],
            profile_versions=list(self.dynamic_weight_service.profile_versions[-1:]),
            reason=(
                "data_quality_abstention_weights_unchanged"
                if data_quality_blocked
                else "signal_cycle_dynamic_weight_update"
            ),
        )

        ensemble = self.model_engine.build_ensemble(model_votes, prediction_time=prediction_time)
        self.storage.save_ensemble_prediction(ensemble)

        multi_timeframe = self.multi_timeframe_service.evaluate(ensemble.ensemble_signal, candles_by_tf, cycle_tf)

        news_state = None
        if getattr(self.runtime, "enable_news_intelligence", True):
            try:
                news_state = self.news_aggregator.aggregate(self.runtime.instrument)
            except Exception as exc:
                self.health_service.record_event("news_intelligence", "WARNING", f"Failed to aggregate news state: {exc}", {})

        strategy_news_state = self._news_state_for_strategy(news_state)
        risk_news_state = self._news_state_for_risk(news_state)

        pre_trade_decision = self.strategy_brain.evaluate(ensemble, snapshot, news_state=strategy_news_state)
        if market_regime.primary_regime == "CHOPPY" and ensemble.ensemble_confidence < 0.70 and ensemble.ensemble_signal != SignalDirection.HOLD:
            pre_trade_decision.blocked_reasons.append("Choppy market regime requires higher model confidence.")
            pre_trade_decision.status = RecommendationStatus.BLOCKED_BY_RISK
        if multi_timeframe.status == "CONFLICT" and ensemble.ensemble_signal != SignalDirection.HOLD:
            pre_trade_decision.blocked_reasons.extend(multi_timeframe.blocked_reasons or ["Multi-timeframe confirmation conflicts with signal."])
            pre_trade_decision.status = RecommendationStatus.BLOCKED_BY_MARKET_STRUCTURE
        if news_risk.status == "BLOCKED" and ensemble.ensemble_signal != SignalDirection.HOLD:
            pre_trade_decision.blocked_reasons.append(news_risk.reason)
            pre_trade_decision.status = RecommendationStatus.BLOCKED_BY_NEWS
            self.health_service.record_event("news_filter", "WARNING", news_risk.reason, news_risk.model_dump())

        trade_plan = None
        entry_plan_candidates = []
        risk_check = None
        final_decision = pre_trade_decision

        if pre_trade_decision.signal in (SignalDirection.BUY, SignalDirection.SELL):
            entry_plan_candidates = self.trade_engine.generate_candidate_plans(
                pre_trade_decision.signal,
                snapshot,
                candles_for_cycle[-1].close,
                ensemble.ensemble_confidence,
                market_regime.primary_regime,
            )
            selected_candidate = self.trade_engine.select_plan(entry_plan_candidates)
            if all(candidate.rejection_reason for candidate in entry_plan_candidates):
                pre_trade_decision.status = RecommendationStatus.BLOCKED_NO_VALID_ENTRY_PLAN
                pre_trade_decision.blocked_reasons.append("No candidate entry plan passed production validation.")
            trade_plan = self.trade_engine.candidate_to_trade_plan(
                selected_candidate,
                candles_for_cycle[-1].close,
                valid_for_minutes=self.trade_engine._valid_for_minutes(snapshot.timeframe),
            )

            risk_check = self.risk_engine.validate(
                trade_plan=trade_plan,
                snapshot=snapshot,
                ensemble=ensemble,
                context=market_context,
                news_state=risk_news_state,
            )

            final_decision = self.strategy_brain.evaluate(
                ensemble=ensemble,
                snapshot=snapshot,
                entry_quality_score=trade_plan.entry_quality_score,
                risk_passed=(risk_check.risk_status.value == "PASSED"),
                news_state=strategy_news_state,
            )
            if news_risk.status == "BLOCKED":
                final_decision.status = RecommendationStatus.BLOCKED_BY_NEWS
                if news_risk.reason not in final_decision.blocked_reasons:
                    final_decision.blocked_reasons.append(news_risk.reason)
            if multi_timeframe.status == "CONFLICT":
                final_decision.status = RecommendationStatus.BLOCKED_BY_MARKET_STRUCTURE
                for reason in multi_timeframe.blocked_reasons or ["Multi-timeframe confirmation conflicts with signal."]:
                    if reason not in final_decision.blocked_reasons:
                        final_decision.blocked_reasons.append(reason)
        else:
            final_decision.status = RecommendationStatus.HOLD

        if data_quality_blocked:
            final_decision.status = RecommendationStatus.HOLD
            final_decision.risk_status = "BLOCKED"
            for reason in report.blocking_reasons:
                message = f"Data quality gate: {reason}"
                if message not in final_decision.blocked_reasons:
                    final_decision.blocked_reasons.append(message)

        self.storage.save_strategy_decision(final_decision)

        recommendation = self.recommendation_builder.build(
            strategy=final_decision,
            snapshot=snapshot,
            ensemble=ensemble,
            risk_check=risk_check,
            model_votes=model_votes,
            trade_plan=trade_plan,
        )
        recommendation.strategy_version = self.runtime.strategy_version
        recommendation.threshold_profile_id = self.threshold_profile.profile_id
        recommendation.model_weight_profile_id = getattr(self.dynamic_weight_service, "active_profile_version", 1)
        health = self.health_service.check_trading_readiness(candles_for_cycle, cycle_tf)
        if health["overall_status"] == "CRITICAL" and recommendation.signal != SignalDirection.HOLD:
            recommendation.status = RecommendationStatus.BLOCKED_BY_SYSTEM_HEALTH
            recommendation.blocked_reasons.extend(health["failed_components"])
            recommendation.risk_status = "BLOCKED"
        self.health_service.record_event(
            "signal",
            "WARNING" if recommendation.blocked_reasons else "HEALTHY",
            f"Generated {recommendation.signal.value} signal with status {recommendation.status.value}.",
            {"signal": recommendation.model_dump(mode="json")},
        )

        recommendation_id = self.storage.save_recommendation(recommendation)
        dynamic_weights_payload = {item.model_name: item.model_dump() for item in dynamic_weight_results}
        self.storage.save_model_signal_predictions(recommendation_id, model_votes, effective_weights)
        self.health_service.record_event("model_weights", "HEALTHY", "Dynamic model weights updated.", dynamic_weights_payload)
        self.storage.save_signal_entry_plans(recommendation_id, [candidate.model_dump() for candidate in entry_plan_candidates])
        self.storage.save_market_regime(recommendation_id, market_regime.model_dump())
        self.storage.save_timeframe_confirmation(recommendation_id, multi_timeframe.model_dump())
        processing_timings_ms["decision"] = round((perf_counter() - stage_started) * 1000.0, 3)
        processing_timings_ms["pre_persistence_total"] = round((perf_counter() - cycle_started) * 1000.0, 3)
        self.storage.save_signal_snapshot(
            self._build_signal_snapshot(
                signal_id=recommendation_id,
                recommendation=recommendation,
                model_votes=model_votes,
                snapshot=snapshot,
                risk_check=risk_check,
                trade_plan=trade_plan,
                market_regime=market_regime.model_dump(),
                multi_timeframe=multi_timeframe.model_dump(),
                dynamic_weights=dynamic_weights_payload,
                entry_plans=[candidate.model_dump() for candidate in entry_plan_candidates],
                news_risk=news_risk.model_dump(),
                health=health,
                data_quality=report.model_dump(mode="json"),
                processing_timings_ms=processing_timings_ms,
            )
        )
        if risk_check is not None:
            self.storage.save_risk_check(risk_check)
        self.validate_signal_outcomes(candles_for_cycle)
        self._send_telegram_alert_if_enabled(recommendation)
        processing_timings_ms["total"] = round((perf_counter() - cycle_started) * 1000.0, 3)

        return CycleResult(
            recommendation=recommendation,
            data_quality_report=report,
            aggregation_counts=aggregation_counts,
            processing_timings_ms=processing_timings_ms,
        )

    def _top_up_native_timeframes(self, aggregation_counts: dict[str, int], minimum_candles: int = 10) -> None:
        for target_tf in ("5m", "15m", "30m", "1h", "4h"):
            existing = self.candle_store.get(self.runtime.instrument, target_tf, limit=minimum_candles)
            if len(existing) >= minimum_candles:
                continue
            try:
                raw = self.candle_provider.fetch_latest_candles(
                    instrument=self.runtime.instrument,
                    timeframe=target_tf,
                    limit=300,
                )
                clean, _report = self.data_engine.clean_candles(
                    raw_candles=raw,
                    instrument=self.runtime.instrument,
                    timeframe=target_tf,
                )
            except Exception as exc:
                aggregation_counts[f"{target_tf}_native_error"] = str(exc)
                continue
            self.candle_store.upsert_many(clean)
            self.storage.save_candles(clean)
            aggregation_counts[f"{target_tf}_native"] = len(clean)

    def validate_signal_outcomes(self, candles: list) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        for recommendation_id, recommendation in self.storage.list_recommendations_with_ids():
            if recommendation.outcome_status in FINAL_OUTCOMES:
                continue

            validation = self.outcome_validator.validate(recommendation, candles)
            recommendation.outcome_status = validation.outcome_status
            recommendation.entry_triggered = validation.entry_triggered
            recommendation.outcome_validated_at = validation.validated_at
            recommendation.realized_rr = validation.realized_rr
            recommendation.max_favorable_move = validation.max_favorable_move
            recommendation.max_adverse_move = validation.max_adverse_move
            recommendation.validation_timeline = validation.timeline or []
            self.storage.update_recommendation(recommendation_id, recommendation)

            if validation.is_final:
                exit_reason = validation.exit_reason or validation.outcome_status
                signal_outcome = SignalOutcome(
                    recommendation_id=recommendation_id,
                    outcome=validation.outcome_status,
                    entry_triggered=validation.entry_triggered,
                    hit_tp1=exit_reason in ("TP1_HIT", "TP2_HIT", "TP3_HIT", "SL_AFTER_TP1", "TP1_ONLY_EXPIRED"),
                    hit_tp2=exit_reason in ("TP2_HIT", "TP3_HIT"),
                    hit_tp3=exit_reason == "TP3_HIT",
                    hit_sl=exit_reason in ("SL_HIT", "SL_AFTER_TP1", "SL_HIT_AMBIGUOUS"),
                    max_favorable_move=validation.max_favorable_move,
                    max_adverse_move=validation.max_adverse_move,
                    realized_rr=validation.realized_rr,
                    closed_at=validation.validated_at,
                    raw_json={"source": "auto_validator", **validation.model_dump()},
                    entry_triggered_at=validation.entry_triggered_at,
                    entry_triggered_price=validation.entry_triggered_price,
                    highest_price_after_signal=validation.highest_price_after_signal,
                    lowest_price_after_signal=validation.lowest_price_after_signal,
                    exit_price=validation.exit_price,
                    exit_reason=validation.exit_reason,
                    pnl_points=validation.pnl_points,
                    pnl_percent=validation.pnl_percent,
                    validation_window_candles=validation.validation_window_candles,
                    ambiguous_candle=validation.ambiguous_candle,
                )
                self.storage.save_outcome(signal_outcome)
                self.health_service.record_event(
                    "signal_validation",
                    "HEALTHY",
                    f"Signal {recommendation_id} validated as {signal_outcome.outcome}.",
                    signal_outcome.raw_json,
                )
                self.storage.save_model_prediction_outcomes(recommendation_id, recommendation, signal_outcome)
                if validation.outcome_status in ("WIN", "LOSS", "PARTIAL_TP", "BREAKEVEN"):
                    self.record_model_outcome(
                        recommendation=recommendation,
                        realized_rr=validation.realized_rr,
                        outcome=validation.outcome_status,
                        source="auto_validator",
                    )

            updates.append({"recommendation_id": recommendation_id, **validation.model_dump()})
        return updates

    def _build_signal_snapshot(
        self,
        signal_id: int,
        recommendation: FinalRecommendation,
        model_votes: list,
        snapshot,
        risk_check,
        trade_plan,
        market_regime: dict[str, Any],
        multi_timeframe: dict[str, Any],
        dynamic_weights: dict[str, Any],
        entry_plans: list[dict[str, Any]],
        news_risk: dict[str, Any],
        health: dict[str, Any],
        data_quality: dict[str, Any],
        processing_timings_ms: dict[str, float],
    ) -> SignalSnapshot:
        indicator_summary = recommendation.indicator_summary
        market_structure = {
            "structure_bias": snapshot.structure_bias,
            "nearest_support": snapshot.nearest_support,
            "nearest_resistance": snapshot.nearest_resistance,
            "session_name": snapshot.session_name,
            "volatility_status": snapshot.volatility_status,
            "atr": snapshot.atr,
        }
        risk_filters = risk_check.model_dump(mode="json") if risk_check is not None else {
            "risk_status": recommendation.risk_status,
            "blocked_reasons": recommendation.blocked_reasons,
        }
        risk_filters["news_filter"] = news_risk
        risk_filters["system_health"] = health
        risk_filters["data_quality"] = data_quality
        risk_filters["processing_timings_ms"] = dict(processing_timings_ms)
        entry_plan = trade_plan.model_dump(mode="json") if trade_plan is not None else {
            "entry_type": None,
            "reason": "No trade plan for HOLD or blocked no-entry recommendation.",
        }
        return SignalSnapshot(
            signal_id=signal_id,
            model_votes_json=[vote.model_dump(mode="json") for vote in model_votes],
            model_weights_json=dict(self.model_engine.model_weights.weights),
            indicator_summary_json=indicator_summary,
            market_structure_json=market_structure,
            risk_filters_json=risk_filters,
            blocked_reasons_json=list(recommendation.blocked_reasons),
            entry_plan_json=entry_plan,
            raw_recommendation_json=recommendation.model_dump(mode="json"),
            market_regime_json=market_regime,
            multi_timeframe_summary_json=multi_timeframe,
            dynamic_weights_json=dynamic_weights,
            entry_plans_json=entry_plans,
        )

    def _send_telegram_alert_if_enabled(self, recommendation: FinalRecommendation) -> None:
        if not self.runtime.enable_telegram_alerts:
            return
        if not self.runtime.telegram_bot_token or not self.runtime.telegram_chat_id:
            self.storage.system_settings["telegram_warning"] = "Telegram alerts enabled but token/chat id are missing."
            return

        config = TelegramConfig(
            bot_token=self.runtime.telegram_bot_token,
            chat_id=self.runtime.telegram_chat_id,
        )
        try:
            result = self.live_control.send_telegram_alert(config, recommendation)
            self.storage.system_settings["last_telegram_alert"] = result
        except Exception as exc:
            self.storage.system_settings["telegram_warning"] = f"Telegram alert failed: {exc}"

    def dashboard_summary(self) -> dict[str, Any]:
        latest = self.storage.latest_recommendation()
        if latest is None:
            return {
                "current_signal": None,
                "model_consensus": None,
                "risk_quality": None,
                "storage_backend": self.storage_backend,
                "dynamic_model_weights": self.model_engine.model_weights.weights,
                "model_artifacts": self.model_engine.artifact_status,
                "today_performance": {
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "pnl": 0.0,
                    "signals": 0,
                },
            }

        return {
            "current_signal": {
                "signal": latest.signal.value,
                "status": latest.status.value,
                "confidence": latest.confidence,
            },
            "model_consensus": latest.model_consensus,
            "risk_quality": latest.risk_status,
            "storage_backend": self.storage_backend,
            "dynamic_model_weights": self.model_engine.model_weights.weights,
            "model_artifacts": self.model_engine.artifact_status,
            "today_performance": {
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "pnl": 0.0,
                "signals": int(self.storage.get_signal_history(page=1, page_size=1).get("total", 0)),
            },
        }

    def record_model_outcome(
        self,
        recommendation: FinalRecommendation,
        realized_rr: float,
        outcome: str,
        source: str,
    ) -> dict[str, Any]:
        self.performance_tracker.record_outcome(
            recommendation=recommendation,
            realized_rr=realized_rr,
            outcome=outcome,
            source=source,
        )

        metrics = self.performance_tracker.metrics()
        for item in metrics.values():
            item["source"] = source

        current_weights = dict(self.model_engine.model_weights.weights)
        if self.runtime.enable_dynamic_model_weights:
            updated_weights = self.performance_tracker.suggested_weights(current_weights)
            self.model_engine.model_weights.weights = updated_weights
        else:
            updated_weights = current_weights

        self.storage.save_model_performance_snapshot(
            metrics=metrics,
            weights=updated_weights,
            source=source,
            timeframe=recommendation.timeframe,
        )
        self.storage.save_model_weight_state(
            weights=updated_weights,
            history=[],
            profile_versions=[],
            reason=f"performance_update:{source}",
        )

        return {
            "metrics": metrics,
            "weights": updated_weights,
            "updated_at": datetime.now(tz=UTC).isoformat(),
        }
