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

_SYSTEM_PROMPT = """
You are deciding whether a user's question could possibly be answered using the available database.

Be VERY PERMISSIVE.

Rules:

- If the question is about employees, departments, salaries, performance, work-life balance, managers, supervisors, training, projects, attendance, hiring, termination, pay, demographics, or any HR-related information, return is_relevant = true.

- Even if an exact column name is NOT present, return true if another related column or table could answer the question.

- NEVER reject a question simply because an exact word is not found in the schema.

- The SQL Generator will determine the correct tables and columns later.

- Only return false when the question is completely unrelated to the database.

Examples of FALSE:
- What's the weather today?
- Who won the FIFA World Cup?
- Tell me a joke.
- What is 2 + 2?

Everything else should usually be TRUE.

Return ONLY JSON:

{
    "is_relevant": true,
    "reason": "short reason"
}
"""

class RelevanceChecker:
    @staticmethod
    def check(question: str, schema_summary: str) -> tuple[bool, str]:
        user_prompt = f"Schema:\n{schema_summary}\n\nQuestion: {question}"
        result = llm_service.complete_json(_SYSTEM_PROMPT, user_prompt)
        is_relevant = bool(result.get("is_relevant", True))
        reason = result.get("reason", "")
        logger.info("Relevance check: %s (%s)", is_relevant, reason)
        return is_relevant, reason
