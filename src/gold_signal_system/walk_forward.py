from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import csv
import json
from pathlib import Path
from typing import Any

from .backtesting import BacktestConfig, BacktestingEngine


@dataclass(slots=True)
class WalkForwardConfig:
    train_size: int = 240
    test_size: int = 80
    step_size: int = 80
    min_window: int = 120
    instrument: str = "XAUUSD"
    timeframe: str = "1m"
    mode: str = "strategy_only"
    model_mode: str = "MOCK_FOR_TEST_ONLY"
    validation_size: int = 80
    model_list: list[str] | None = None
    feature_config: dict[str, Any] | None = None
    threshold_config: dict[str, Any] | None = None
    output_artifact_path: str | None = None
    metrics_output_path: str | None = None


class WalkForwardBacktestService:
    def __init__(self, system, reports_dir: str = "reports") -> None:
        self.system = system
        self.reports_dir = Path(reports_dir) / "walk_forward"
        self.runs: list[dict[str, Any]] = []
        self.windows: dict[int, list[dict[str, Any]]] = {}
        self.signals: dict[int, list[dict[str, Any]]] = {}

    def generate_windows(self, candles: list[dict], config: WalkForwardConfig) -> list[dict[str, Any]]:
        windows: list[dict[str, Any]] = []
        start = 0
        while start + config.train_size + config.test_size <= len(candles):
            train_start = start
            train_end = start + config.train_size
            test_start = train_end
            test_end = test_start + config.test_size
            windows.append(
                {
                    "train_start_index": train_start,
                    "train_end_index": train_end,
                    "test_start_index": test_start,
                    "test_end_index": test_end,
                    "train_start": candles[train_start]["candle_time"],
                    "train_end": candles[train_end - 1]["candle_time"],
                    "test_start": candles[test_start]["candle_time"],
                    "test_end": candles[test_end - 1]["candle_time"],
                }
            )
            start += config.step_size
        return windows

    def run(
        self,
        candles: list[dict],
        config: WalkForwardConfig | None = None,
        name: str = "walk_forward",
        run_id: str | None = None,
    ) -> dict[str, Any]:
        config = config or WalkForwardConfig()
        numeric_id = len(self.runs) + 1
        durable_run_id = run_id or f"WF-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{numeric_id:03d}"
        windows = self.generate_windows(candles, config)
        window_reports: list[dict[str, Any]] = []
        backtester = BacktestingEngine(self.system, BacktestConfig(min_window=config.min_window))

        for idx, window in enumerate(windows, start=1):
            test_candles = candles[: window["test_end_index"]]
            report = backtester.run(test_candles, source_timeframe=config.timeframe)
            summary = {
                "window_id": idx,
                **window,
                "summary": {
                    "total_signals": report.get("trades", 0),
                    "win_rate": report.get("win_rate", 0.0),
                    "profit_factor": report.get("profit_factor", 0.0),
                    "net_points": report.get("equity", 0.0),
                    "max_drawdown": report.get("max_drawdown", 0.0),
                    "average_rr": report.get("average_rr", 0.0),
                },
            }
            window_reports.append(summary)

        total_trades = sum(item["summary"]["total_signals"] for item in window_reports)
        avg_win_rate = (
            sum(item["summary"]["win_rate"] for item in window_reports) / len(window_reports)
            if window_reports
            else 0.0
        )
        avg_profit_factor = (
            sum(item["summary"]["profit_factor"] for item in window_reports) / len(window_reports)
            if window_reports
            else 0.0
        )
        run = {
            "id": numeric_id,
            "run_id": durable_run_id,
            "run_type": "WALK_FORWARD",
            "name": name,
            "instrument": config.instrument,
            "timeframe": config.timeframe,
            "started_at": datetime.now(tz=UTC).isoformat(),
            "completed_at": datetime.now(tz=UTC).isoformat(),
            "status": "COMPLETED",
            "config": asdict(config),
            "summary": {
                "windows": len(window_reports),
                "total_signals": total_trades,
                "recommended_signals": total_trades,
                "blocked_signals": 0,
                "win_rate": round(avg_win_rate, 4),
                "profit_factor": round(avg_profit_factor, 4),
                "max_drawdown": round(max((item["summary"].get("max_drawdown", 0.0) for item in window_reports), default=0.0), 4),
                "average_rr": round(
                    sum(item["summary"].get("average_rr", 0.0) for item in window_reports) / len(window_reports),
                    4,
                ) if window_reports else 0.0,
                "number_of_trades": total_trades,
                "buy_precision": 0.0,
                "sell_precision": 0.0,
                "model_mode": config.model_mode,
                "model_by_model": self.system.performance_tracker.metrics(),
            },
        }
        report_dir = self._write_reports(run, window_reports)
        run["report_dir"] = str(report_dir)
        run["report_path"] = str(report_dir / "summary.json")
        self.runs.append(run)
        self.windows[numeric_id] = window_reports
        self.signals[numeric_id] = list(self.system.storage.backtest_trades[-total_trades:]) if total_trades else []
        self.windows[durable_run_id] = window_reports
        self.signals[durable_run_id] = self.signals[numeric_id]
        return run

    def _write_reports(self, run: dict[str, Any], window_reports: list[dict[str, Any]]) -> Path:
        report_dir = self.reports_dir / str(run.get("run_id") or f"run_{run['id']}")
        report_dir.mkdir(parents=True, exist_ok=True)
        trades = list(self.system.storage.backtest_trades) if self.system is not None else []
        model_metrics = run["summary"].get("model_by_model", {})

        (report_dir / "summary.json").write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")

        with (report_dir / "folds.csv").open("w", encoding="utf-8", newline="") as handle:
            fieldnames = [
                "fold_number", "train_start", "train_end", "test_start", "test_end",
                "number_of_signals", "number_of_trades", "win_rate", "profit_factor",
                "max_drawdown", "average_rr", "buy_precision", "sell_precision",
                "blocked_signals", "best_thresholds", "model_weights_used",
            ]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for fold in window_reports:
                summary = fold["summary"]
                writer.writerow(
                    {
                        "fold_number": fold["window_id"],
                        "train_start": fold["train_start"],
                        "train_end": fold["train_end"],
                        "test_start": fold["test_start"],
                        "test_end": fold["test_end"],
                        "number_of_signals": summary.get("total_signals", 0),
                        "number_of_trades": summary.get("total_signals", 0),
                        "win_rate": summary.get("win_rate", 0.0),
                        "profit_factor": summary.get("profit_factor", 0.0),
                        "max_drawdown": summary.get("max_drawdown", 0.0),
                        "average_rr": summary.get("average_rr", 0.0),
                        "buy_precision": 0.0,
                        "sell_precision": 0.0,
                        "blocked_signals": 0,
                        "best_thresholds": json.dumps(run["config"].get("threshold_config") or {}),
                        "model_weights_used": json.dumps(self._model_weights()),
                    }
                )

        with (report_dir / "trades.csv").open("w", encoding="utf-8", newline="") as handle:
            fieldnames = sorted({key for trade in trades for key in trade.keys()}) if trades else ["time", "signal", "outcome", "realized_rr"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(trades)

        with (report_dir / "model_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
            fieldnames = ["model_name", "win_rate", "buy_precision", "sell_precision", "observations"]
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for model_name, metrics in model_metrics.items():
                writer.writerow({
                    "model_name": model_name,
                    "win_rate": metrics.get("win_rate", 0.0),
                    "buy_precision": metrics.get("buy_precision", 0.0),
                    "sell_precision": metrics.get("sell_precision", 0.0),
                    "observations": metrics.get("observations", 0),
                })

        with (report_dir / "strategy_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
            writer.writeheader()
            for key, value in run["summary"].items():
                if key != "model_by_model":
                    writer.writerow({"metric": key, "value": value})

        (report_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "summary": run["summary"],
                    "model_metrics": model_metrics,
                    "model_mode": run.get("config", {}).get("model_mode", "MOCK_FOR_TEST_ONLY"),
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        (report_dir / "recommendations.md").write_text(
            "# Walk-Forward Recommendations\n\n"
            "- Review folds with low trade count before activation.\n"
            "- Compare validation and unseen periods before trusting optimization results.\n"
            "- Model retraining mode is prepared through config fields but requires trained artifact integration.\n",
            encoding="utf-8",
        )
        return report_dir

    def _model_weights(self) -> dict[str, float]:
        if self.system is None:
            return {}
        model_weights = getattr(getattr(self.system, "model_engine", None), "model_weights", None)
        weights = getattr(model_weights, "weights", None)
        return dict(weights) if isinstance(weights, dict) else {}
