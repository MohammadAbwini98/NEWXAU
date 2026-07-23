from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .contracts import FinalRecommendation, MarketContext, SignalDirection
from .pipeline import GoldSignalSystem


@dataclass(slots=True)
class BacktestConfig:
    spread: float = 0.25
    commission_per_trade: float = 0.0
    slippage: float = 0.05
    horizon_candles: int = 12
    min_window: int = 180


class BacktestingEngine:
    """Phase 8: historical replay, simulated outcomes, and metrics."""

    def __init__(self, system: GoldSignalSystem, config: BacktestConfig | None = None) -> None:
        self.system = system
        self.config = config or BacktestConfig()

    def run(self, candles: list[dict], source_timeframe: str = "1m") -> dict[str, Any]:
        trades: list[dict[str, Any]] = []
        equity = 0.0
        equity_curve: list[float] = []
        gross_profit = 0.0
        gross_loss = 0.0
        wins = 0
        blocked_signals = 0
        total_signals = 0
        total_trading_cost_rr = 0.0

        for i in range(self.config.min_window, len(candles) - self.config.horizon_candles):
            window = candles[:i]
            result = self.system.run_signal_cycle(
                raw_candles=window,
                source_timeframe=source_timeframe,
                market_context=MarketContext(spread=self.config.spread),
            )
            rec = result.recommendation
            total_signals += 1
            if rec.blocked_reasons or rec.status.value.startswith("BLOCKED"):
                blocked_signals += 1
            if rec.signal == SignalDirection.HOLD or rec.entry_price is None or rec.stop_loss is None:
                continue

            future = candles[i : i + self.config.horizon_candles]
            outcome = self._simulate_outcome(rec, future)
            pnl = float(outcome["realized_rr"])
            total_trading_cost_rr += float(outcome["trading_cost_rr"])
            equity += pnl
            equity_curve.append(equity)

            if pnl > 0:
                wins += 1
                gross_profit += pnl
            elif pnl < 0:
                gross_loss += abs(pnl)

            trade = {
                "time": rec.signal_time.isoformat(),
                "signal": rec.signal.value,
                "status": rec.status.value,
                "entry": rec.entry_price,
                "stop_loss": rec.stop_loss,
                "tp1": rec.take_profit_1,
                "tp2": rec.take_profit_2,
                "tp3": rec.take_profit_3,
                "risk_reward": rec.risk_reward,
                "outcome": outcome["outcome"],
                "realized_rr": outcome["realized_rr"],
                "gross_realized_rr": outcome["gross_realized_rr"],
                "trading_cost_rr": outcome["trading_cost_rr"],
                "max_favorable_move": outcome["max_favorable_move"],
                "max_adverse_move": outcome["max_adverse_move"],
            }
            trades.append(trade)

            self.system.record_model_outcome(
                recommendation=rec,
                realized_rr=float(outcome["realized_rr"]),
                outcome=str(outcome["outcome"]),
                source="backtest",
            )

        trade_count = len(trades)
        win_rate = (wins / trade_count) if trade_count else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
        max_drawdown = self._max_drawdown(equity_curve)
        avg_rr = (sum(t["realized_rr"] for t in trades) / trade_count) if trade_count else 0.0
        avg_gross_rr = (sum(t["gross_realized_rr"] for t in trades) / trade_count) if trade_count else 0.0
        buy_trades = [t for t in trades if t.get("signal") == "BUY"]
        sell_trades = [t for t in trades if t.get("signal") == "SELL"]
        buy_precision = self._precision(buy_trades)
        sell_precision = self._precision(sell_trades)

        report = {
            "run_time": datetime.now(tz=UTC).isoformat(),
            "total_signals": total_signals,
            "trades": trade_count,
            "number_of_trades": trade_count,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "max_drawdown": round(max_drawdown, 4),
            "average_rr": round(avg_rr, 4),
            "average_gross_rr": round(avg_gross_rr, 4),
            "buy_precision": round(buy_precision, 4),
            "sell_precision": round(sell_precision, 4),
            "blocked_signals": blocked_signals,
            "total_trading_cost_rr": round(total_trading_cost_rr, 4),
            "cost_assumptions": {
                "spread_points": self.config.spread,
                "slippage_points_per_fill": self.config.slippage,
                "commission_rr_per_trade": self.config.commission_per_trade,
                "round_trip_price_cost_points": self.config.spread + (2.0 * self.config.slippage),
            },
            "equity": round(equity, 4),
            "model_performance": self.system.performance_tracker.metrics(),
            "dynamic_model_weights": self.system.model_engine.model_weights.weights,
            "trade_simulation": trades,
        }

        self.system.storage.backtest_runs.append(report)
        self.system.storage.backtest_trades.extend(trades)
        return report

    def _simulate_outcome(self, rec: FinalRecommendation, future_candles: list[dict]) -> dict[str, float | str]:
        if rec.entry_price is None or rec.stop_loss is None:
            return {
                "outcome": "NO_ENTRY",
                "realized_rr": 0.0,
                "gross_realized_rr": 0.0,
                "trading_cost_rr": 0.0,
                "max_favorable_move": 0.0,
                "max_adverse_move": 0.0,
            }

        direction = rec.signal
        entry = rec.entry_price
        sl = rec.stop_loss
        tp1 = rec.take_profit_1
        tp2 = rec.take_profit_2
        tp3 = rec.take_profit_3

        max_fav = 0.0
        max_adv = 0.0
        outcome = "EXPIRED"
        gross_realized_rr = 0.0

        risk = abs(entry - sl) if abs(entry - sl) > 0 else 0.0001

        for row in future_candles:
            high = float(row["high"])
            low = float(row["low"])

            if direction == SignalDirection.BUY:
                max_fav = max(max_fav, high - entry)
                max_adv = min(max_adv, low - entry)

                if low <= sl:
                    outcome = "SL_HIT"
                    gross_realized_rr = -1.0
                    break
                if tp3 is not None and high >= tp3:
                    outcome = "TP3_HIT"
                    gross_realized_rr = abs(tp3 - entry) / risk
                    break
                if tp2 is not None and high >= tp2:
                    outcome = "TP2_HIT"
                    gross_realized_rr = abs(tp2 - entry) / risk
                    break
                if tp1 is not None and high >= tp1:
                    outcome = "TP1_HIT"
                    gross_realized_rr = abs(tp1 - entry) / risk
            else:
                max_fav = max(max_fav, entry - low)
                max_adv = min(max_adv, entry - high)

                if high >= sl:
                    outcome = "SL_HIT"
                    gross_realized_rr = -1.0
                    break
                if tp3 is not None and low <= tp3:
                    outcome = "TP3_HIT"
                    gross_realized_rr = abs(entry - tp3) / risk
                    break
                if tp2 is not None and low <= tp2:
                    outcome = "TP2_HIT"
                    gross_realized_rr = abs(entry - tp2) / risk
                    break
                if tp1 is not None and low <= tp1:
                    outcome = "TP1_HIT"
                    gross_realized_rr = abs(entry - tp1) / risk

        round_trip_price_cost = self.config.spread + (2.0 * self.config.slippage)
        trading_cost_rr = (round_trip_price_cost / risk) + self.config.commission_per_trade
        realized_rr = gross_realized_rr - trading_cost_rr

        return {
            "outcome": outcome,
            "realized_rr": round(realized_rr, 4),
            "gross_realized_rr": round(gross_realized_rr, 4),
            "trading_cost_rr": round(trading_cost_rr, 4),
            "max_favorable_move": round(max_fav, 4),
            "max_adverse_move": round(abs(max_adv), 4),
        }

    def _max_drawdown(self, equity_curve: list[float]) -> float:
        if not equity_curve:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
        return max_dd

    def _precision(self, trades: list[dict[str, Any]]) -> float:
        if not trades:
            return 0.0
        wins = sum(1 for trade in trades if float(trade.get("realized_rr") or 0.0) > 0)
        return wins / len(trades)
