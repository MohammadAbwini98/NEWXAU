from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from gold_signal_system.storage import PostgreSQLStorage
from gold_signal_system.news_intelligence.repository import NewsIntelligenceRepository


def test_postgres_connection_uses_bounded_startup_timeout() -> None:
    connection = MagicMock()

    with (
        patch("psycopg.connect", return_value=connection) as connect,
        patch.object(PostgreSQLStorage, "_configure_schema"),
    ):
        storage = PostgreSQLStorage(
            "postgresql://example.invalid/newxau",
            connect_timeout_seconds=7,
        )

    connect.assert_called_once()
    assert connect.call_args.kwargs["connect_timeout"] == 7
    storage.close()


def test_news_repository_connection_uses_bounded_startup_timeout() -> None:
    connection = MagicMock()

    with patch("psycopg.connect", return_value=connection) as connect:
        repository = NewsIntelligenceRepository(
            "postgresql://example.invalid/newxau",
            connect_timeout_seconds=9,
        )

    connect.assert_called_once()
    assert connect.call_args.kwargs["connect_timeout"] == 9
    repository.close()
