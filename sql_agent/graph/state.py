"""TypedDict describing the state threaded through every graph node."""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from models.schema_models import DatabaseSchema


class AgentState(TypedDict, total=False):
    # input
    question: str
    original_question: str

    # schema inspector node
    schema: DatabaseSchema
    schema_summary: str

    # intent understanding node
    intent: str

    # relevance checker node
    is_relevant: bool
    relevance_reason: str

    # table selection node
    selected_tables: list[str]

    # sql generation / execution / validation
    generated_sql: Optional[str]
    sql_rows: list[dict[str, Any]]
    execution_time_ms: float
    sql_error: Optional[str]
    retry_count: int

    # response generator
    final_answer: str
