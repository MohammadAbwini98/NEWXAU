from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import gold_signal_system.config as config_module
from gold_signal_system.config import RuntimeConfig


class RuntimeConfigDefaultsTests(unittest.TestCase):
    def test_gold_defaults_are_used_without_instrument_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TRADING_INSTRUMENT": "",
                "INSTRUMENT": "",
                "CAPITALCOM_EPIC": "",
                "CAPITAL_DEFAULT_EPIC": "",
                "TRADING_PROVIDER_SYMBOL": "",
            },
        ):
            runtime = RuntimeConfig(data_provider="synthetic", postgres_dsn=None)

        self.assertEqual(runtime.instrument, "XAUUSD")
        self.assertEqual(runtime.capitalcom_epic, "GOLD")

    def test_external_capital_env_file_is_explicit_only(self) -> None:
        self.assertFalse(hasattr(config_module, "DEFAULT_CAPITAL_ENV_FILE"))


if __name__ == "__main__":
    unittest.main()
