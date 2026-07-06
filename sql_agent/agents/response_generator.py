"""
Response Generator Node.

Converts raw SQL result rows into a clear, human-readable natural
language answer. Receives only the question and the result rows -- never
writes or sees the schema-inference logic.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You explain SQL query results to a business user in clear, natural \
language. Be concise and specific -- reference actual values/numbers from the results. \
If the result set is empty, say plainly that no matching data was found. \
The result rows are already the final query output, not source data to parse. \
Do not mention SQL, tables, or databases in your answer -- just answer the question. \
Respond ONLY with strict JSON: {"answer": "<plain text answer>"}. Do not include markdown, \
code fences, HTML, SQL, Python, pandas, DataFrame examples, or JSON outside this object."""


class ResponseGenerator:
    @staticmethod
    def generate(question: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No matching data was found for your question."

        preview = rows[:25]  # cap payload size sent to the LLM
        payload = json.dumps(preview, default=str)
        user_prompt = (
            f"User question: {question}\n\n"
            f"Final result rows to summarize ({len(rows)} total rows, first {len(preview)} shown):\n"
            f"{payload}\n\n"
            "Write the business answer only. Do not explain how to load, parse, or analyze this data."
        )
        result = llm_service.complete_json(_SYSTEM_PROMPT, user_prompt)
        answer = result.get("answer", "")
        cleaned = ResponseGenerator._plain_text(answer) if isinstance(answer, str) else ""
        if not cleaned or ResponseGenerator._looks_like_code_help(cleaned):
            return ResponseGenerator._deterministic_summary(question, rows)
        return cleaned

    @staticmethod
    def friendly_irrelevant_response(question: str, reason: str) -> str:
        return (
            "I couldn't find a way to answer that from the currently loaded data. "
            f"{reason} Try asking something related to the uploaded datasets."
        )

    @staticmethod
    def friendly_failure_response(question: str) -> str:
        return (
            "I attempted to answer this question but the generated queries kept failing. "
            "Try rephrasing the question or check that the relevant data was uploaded."
        )

    @staticmethod
    def _plain_text(answer: str) -> str:
        cleaned = re.sub(r"```(?:\w+)?\s*([\s\S]*?)```", r"\1", answer).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("answer"), str):
            cleaned = parsed["answer"]
        cleaned = re.sub(r"</?[^>]+>", "", cleaned)
        cleaned = cleaned.replace("{", "").replace("}", "").strip()
        return cleaned

    @staticmethod
    def _looks_like_code_help(answer: str) -> bool:
        lowered = answer.lower()
        code_markers = (
            "import pandas",
            "dataframe",
            "pd.",
            "df[",
            "print(",
            "sample code",
            "parse this data",
            "list of dictionaries",
            "assuming 'data'",
        )
        return any(marker in lowered for marker in code_markers)

    @staticmethod
    def _deterministic_summary(question: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No matching data was found for your question."

        if len(rows) == 1:
            return ResponseGenerator._single_row_summary(rows[0])

        label_col, value_col = ResponseGenerator._label_value_columns(rows)
        if label_col and value_col:
            parts = [
                f"{row.get(label_col)}: {ResponseGenerator._format_value(row.get(value_col))}"
                for row in rows[:10]
            ]
            suffix = f" Showing the first 10 of {len(rows)} results." if len(rows) > 10 else ""
            return f"Here are the results: {', '.join(parts)}.{suffix}"

        preview = rows[:5]
        return f"I found {len(rows)} matching rows. First results: {preview}"

    @staticmethod
    def _single_row_summary(row: dict[str, Any]) -> str:
        if not row:
            return "No matching data was found for your question."

        non_null_items = [(key, value) for key, value in row.items() if value is not None]
        if not non_null_items:
            return "No matching value was found for your question."

        if len(non_null_items) == 1:
            key, value = non_null_items[0]
            return f"The {ResponseGenerator._friendly_column_name(key)} is {ResponseGenerator._format_value(value)}."

        parts = [
            f"{ResponseGenerator._friendly_column_name(key)}: {ResponseGenerator._format_value(value)}"
            for key, value in non_null_items[:8]
        ]
        return f"Here are the key results: {', '.join(parts)}."

    @staticmethod
    def _label_value_columns(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
        columns = list(rows[0].keys())
        label_cols = [
            column for column in columns
            if any(not ResponseGenerator._is_number(row.get(column)) for row in rows[:10])
        ]
        value_cols = [
            column for column in columns
            if all(row.get(column) is None or ResponseGenerator._is_number(row.get(column)) for row in rows[:10])
        ]
        if label_cols and value_cols:
            return label_cols[0], value_cols[-1]
        return None, None

    @staticmethod
    def _friendly_column_name(column: str) -> str:
        normalized = column.strip()
        aggregate_match = re.match(r"(?i)(sum|avg|count|min|max)\((.+)\)", normalized)
        if aggregate_match:
            operation, inner = aggregate_match.groups()
            friendly_inner = inner.replace("_", " ").replace("*", "rows")
            operation_names = {
                "sum": "total",
                "avg": "average",
                "count": "count",
                "min": "minimum",
                "max": "maximum",
            }
            return f"{operation_names.get(operation.lower(), operation.lower())} {friendly_inner}".strip()
        return normalized.replace("_", " ")

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None:
            return "not available"
        if isinstance(value, float):
            if math.isfinite(value):
                return f"{value:,.2f}"
            return str(value)
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    @staticmethod
    def _is_number(value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
