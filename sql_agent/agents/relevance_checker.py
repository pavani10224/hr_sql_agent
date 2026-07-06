"""
Relevance Checker Node.

Decides whether the current database (as described by its dynamic schema
summary) could plausibly answer the question at all, before we spend
effort selecting tables / generating SQL.
"""
from __future__ import annotations

from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You decide whether a question can plausibly be answered using ONLY the \
database schema provided below. Respond ONLY with strict JSON: \
{"is_relevant": true|false, "reason": "<short reason>"}. \
Be permissive: if the schema's tables/columns could reasonably relate to the question, \
mark it relevant. Only mark it irrelevant if the question is clearly about something the \
schema has no plausible way of answering (e.g. asking about weather when the schema is HR data). \
Treat paraphrases, synonyms, spacing differences, and hyphenation as potentially relevant."""


class RelevanceChecker:
    @staticmethod
    def check(question: str, schema_summary: str) -> tuple[bool, str]:
        user_prompt = f"Schema:\n{schema_summary}\n\nQuestion: {question}"
        result = llm_service.complete_json(_SYSTEM_PROMPT, user_prompt)
        is_relevant = bool(result.get("is_relevant", True))
        reason = result.get("reason", "")
        logger.info("Relevance check: %s (%s)", is_relevant, reason)
        return is_relevant, reason
