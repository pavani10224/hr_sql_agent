"""
Small in-memory store for state that needs to survive across requests
within a single running process (current schema cache, last generated
SQL for the /generated_sql endpoint). Not a database -- just process
memory, rebuilt whenever a new CSV batch is uploaded.
"""
from __future__ import annotations

from typing import Optional

from models.schema_models import DatabaseSchema


class AppState:
    def __init__(self) -> None:
        self.schema: Optional[DatabaseSchema] = None
        self.last_question: Optional[str] = None
        self.last_sql: Optional[str] = None
        self.last_tables_used: list[str] = []

    def set_schema(self, schema: DatabaseSchema) -> None:
        self.schema = schema

    def record_query(self, question: str, sql: Optional[str], tables_used: list[str]) -> None:
        self.last_question = question
        self.last_sql = sql
        self.last_tables_used = tables_used


app_state = AppState()
