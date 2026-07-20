from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.paper_trading import PaperTradingEngine
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.utils import generate_synthetic_candles


def main() -> None:
    system = GoldSignalSystem()
    paper = PaperTradingEngine(system)

    for i in range(5):
        candles = generate_synthetic_candles(count=900 + i * 5, timeframe="1m")
        cycle = paper.run_cycle(candles, source_timeframe="1m")
        print(f"Cycle {i + 1}: {cycle['signal']} / {cycle['status']} / conf={cycle['confidence']:.2f}")

    print("=== Drift Report ===")
    print(json.dumps(paper.drift_report(), indent=2))


if __name__ == "__main__":
    main()
