"""Executes model-generated SQL and normalizes the raw text first."""
from __future__ import annotations

import re
from typing import Any

from database.db_manager import db_manager
from utils.logger import get_logger

logger = get_logger(__name__)


class QueryExecutor:
    @staticmethod
    def clean_sql(raw_sql: str) -> str:
        """Strip markdown code fences / stray prose the LLM sometimes adds."""
        text = raw_sql.strip()
        fence_match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()
        # If the model still prefixed prose before the statement, take from
        # the first SELECT/WITH onward.
        lower = text.lower()
        start = min((idx for idx in (lower.find("select"), lower.find("with")) if idx != -1), default=0)
        text = text[start:].strip()
        return text.rstrip(";").strip()

    def run(self, raw_sql: str) -> tuple[str, list[dict[str, Any]], float]:
        clean = self.clean_sql(raw_sql)
        rows, elapsed_ms = db_manager.execute_query(clean)
        return clean, rows, elapsed_ms


query_executor = QueryExecutor()
