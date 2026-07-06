"""Thin wrapper around a SQLAlchemy engine for the active SQLite database."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config import settings
from utils.exceptions import NoDatabaseError, SQLExecutionError, UnsafeSQLError
from utils.logger import get_logger

logger = get_logger(__name__)

_UNSAFE_KEYWORDS = (
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "attach", "detach", "pragma", "replace",
)


class DatabaseManager:
    """Singleton-ish holder for the current SQLite engine.

    Recreated whenever a new CSV batch is uploaded (see upload router).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.sqlite_db_path
        self._engine: Engine | None = None

    def is_ready(self) -> bool:
        return self.db_path.exists()

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            if not self.is_ready():
                raise NoDatabaseError("No database has been built yet. Upload CSV files first.")
            self._engine = create_engine(f"sqlite:///{self.db_path}")
        return self._engine

    def refresh(self) -> None:
        """Dispose of any cached engine so the next access re-opens the file
        (called after a new upload replaces the .db file)."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    @staticmethod
    def _assert_read_only(sql: str) -> None:
        normalized = sql.strip().lower()
        if not normalized.startswith("select") and not normalized.startswith("with"):
            raise UnsafeSQLError("Only SELECT statements are permitted.")
        for keyword in _UNSAFE_KEYWORDS:
            if keyword in normalized:
                raise UnsafeSQLError(f"Generated SQL contains a disallowed keyword: '{keyword}'.")

    def execute_query(self, sql: str) -> tuple[list[dict[str, Any]], float]:
        """Execute a read-only SQL query and return (rows, elapsed_ms)."""
        self._assert_read_only(sql)
        start = time.perf_counter()
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = [dict(zip(columns, row)) for row in result.fetchall()]
        except UnsafeSQLError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SQLExecutionError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000
        return rows, elapsed_ms


db_manager = DatabaseManager()
