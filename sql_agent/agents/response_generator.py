"""
Response Generator Node.

Converts raw SQL result rows into a clear, human-readable natural
language answer. Receives only the question and the result rows -- never
writes or sees the schema-inference logic.
"""
from __future__ import annotations

from typing import Any

from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You explain SQL query results to a business user in clear, natural \
language. Be concise and specific -- reference actual values/numbers from the results. \
If the result set is empty, say plainly that no matching data was found. \
Do not mention SQL, tables, or databases in your answer -- just answer the question."""


class ResponseGenerator:
    @staticmethod
    def generate(question: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No matching data was found for your question."

        preview = rows[:25]  # cap payload size sent to the LLM
        user_prompt = f"Question: {question}\n\nResult rows ({len(rows)} total): {preview}"
        answer = llm_service.complete(_SYSTEM_PROMPT, user_prompt)
        return answer or "I found results, but could not summarize them."

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
