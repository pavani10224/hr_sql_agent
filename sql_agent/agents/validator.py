"""
SQL Execution + Validation Node.

Executes the generated SQL, and validates:
    - it actually ran (no syntax/execution error)
    - it returned rows (empty result sets are flagged, not treated as a hard
      failure -- they're valid answers to some questions, e.g. "how many
      employees earn over 10 million?")
"""
from __future__ import annotations

from typing import Any

from services.query_executor import query_executor
from utils.exceptions import SQLExecutionError, UnsafeSQLError
from utils.logger import get_logger

logger = get_logger(__name__)


class SQLValidator:
    @staticmethod
    def execute_and_validate(raw_sql: str) -> dict[str, Any]:
        """Returns a dict with keys: success, sql, rows, elapsed_ms, error, is_empty."""
        try:
            clean_sql, rows, elapsed_ms = query_executor.run(raw_sql)
        except (SQLExecutionError, UnsafeSQLError) as exc:
            logger.warning("SQL execution failed: %s", exc)
            return {
                "success": False,
                "sql": raw_sql,
                "rows": [],
                "elapsed_ms": 0.0,
                "error": str(exc),
                "is_empty": True,
            }

        return {
            "success": True,
            "sql": clean_sql,
            "rows": rows,
            "elapsed_ms": elapsed_ms,
            "error": None,
            "is_empty": len(rows) == 0,
        }
