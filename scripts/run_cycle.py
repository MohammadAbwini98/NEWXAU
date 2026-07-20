from __future__ import annotations

import json
import os
import sys
import argparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.contracts import MarketContext
from gold_signal_system.pipeline import GoldSignalSystem
from gold_signal_system.utils import generate_synthetic_candles


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one XAUUSD Signal System cycle.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use generated mock candles instead of fetching live candles from Capital.com.",
    )
    args = parser.parse_args()

    system = GoldSignalSystem()
    if args.mock:
        candles = generate_synthetic_candles(count=900, timeframe="1m")
        result = system.run_signal_cycle(
            raw_candles=candles,
            source_timeframe="1m",
            market_context=MarketContext(spread=0.24),
        )
    else:
        result = system.run_live_cycle(
            source_timeframe="1m",
            market_context=MarketContext(spread=0.24),
        )

    print("=== Data Quality Report ===")
    print(json.dumps(result.data_quality_report.model_dump(mode="json"), indent=2))
    print("=== Aggregations ===")
    print(json.dumps(result.aggregation_counts, indent=2))
    print("=== Final Recommendation ===")
    print(json.dumps(result.recommendation.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
