from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.backtesting import BacktestingEngine
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.utils import generate_synthetic_candles


def main() -> None:
    system = GoldSignalSystem()
    engine = BacktestingEngine(system)
    candles = generate_synthetic_candles(count=1400, timeframe="1m")
    report = engine.run(candles, source_timeframe="1m")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
