from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

os.environ["POSTGRES_DSN"] = ""

from scripts import run_backend


class DesktopBackendRunnerTests(unittest.TestCase):
    def test_desktop_database_initialization_reports_success(self) -> None:
        output = StringIO()
        with (
            patch.object(
                run_backend,
                "initialize_database",
                return_value={"status": "OK", "schema": "newxau"},
            ),
            redirect_stdout(output),
        ):
            run_backend.initialize_desktop_database()

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["event"], "database.initialized")
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["schema"], "newxau")

    def test_desktop_database_initialization_fails_open_without_secret_details(self) -> None:
        output = StringIO()
        secret = "postgresql://newxau_app:top-secret@127.0.0.1/newxau"
        with (
            patch.object(
                run_backend,
                "initialize_database",
                side_effect=RuntimeError(secret),
            ),
            redirect_stdout(output),
        ):
            run_backend.initialize_desktop_database()

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["event"], "database.warning")
        self.assertEqual(payload["status"], "ERROR")
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertNotIn(secret, output.getvalue())
        self.assertIn("configured fallback", payload["message"])


if __name__ == "__main__":
    unittest.main()
