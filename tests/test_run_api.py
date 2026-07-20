from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.run_api import _pids_from_windows_netstat
from scripts import run_api


class RunApiTests(unittest.TestCase):
    def test_windows_netstat_parser_finds_dashboard_port_pids(self) -> None:
        output = """
  Proto  Local Address          Foreign Address        State           PID
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       1234
  TCP    0.0.0.0:9000           0.0.0.0:0              LISTENING       5678
  TCP    [::1]:8000             [::]:0                 LISTENING       9012
"""

        self.assertEqual(_pids_from_windows_netstat(output, 8000), {1234, 9012})

    def test_open_dashboard_uses_local_dashboard_url(self) -> None:
        opened: list[str] = []
        original_thread = run_api.threading.Thread
        original_open = run_api.webbrowser.open
        original_sleep = run_api.time.sleep

        class ImmediateThread:
            def __init__(self, target, daemon=False) -> None:
                self.target = target
                self.daemon = daemon

            def start(self) -> None:
                self.target()

        try:
            run_api.threading.Thread = ImmediateThread
            run_api.time.sleep = lambda _seconds: None
            run_api.webbrowser.open = lambda url: opened.append(url)

            run_api.open_dashboard_when_ready("127.0.0.1", 8000)
        finally:
            run_api.threading.Thread = original_thread
            run_api.webbrowser.open = original_open
            run_api.time.sleep = original_sleep

        self.assertEqual(opened, ["http://127.0.0.1:8000/"])


if __name__ == "__main__":
    unittest.main()
