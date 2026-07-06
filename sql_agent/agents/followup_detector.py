"""
Conversation follow-up resolver.

This keeps conversational context outside the LangGraph topology: the router
turns the user's current message into a standalone database question before the
existing graph starts.
"""
from __future__ import annotations

import re
from typing import Any

from models.schema_models import DatabaseSchema
from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SHORTCUT_RE = re.compile(r"^\s*(?:emp|employee|id)\s*[:#-]?\s*(\d+)\s*$", re.IGNORECASE)
_NAME_FIELD_RE = re.compile(r"^\s*([a-z][a-z'-]{1,})\s+([a-z][a-z'-]{1,})\s+(.+?)\s*$", re.IGNORECASE)
_VAGUE_TRAINING_PROGRAM_RE = re.compile(
    r"\b(?:this|that|current|previous|selected|mentioned)\s+training\s+program\b",
    re.IGNORECASE,
)
_NON_NAME_TERMS = {
    "department",
    "employee",
    "employees",
    "payzone",
    "show",
    "trainer",
    "training",
    "worklife",
    "zone",
}

_SYSTEM_PROMPT = """You rewrite a user's current database question into a standalone question.
Use the conversation history only when the current question is truly a follow-up.
Resolve pronouns and vague references such as his, her, their, those, that group, same zone,
same department, or previous result to the specific entity or filter from history.
If the current question starts a new topic or is already standalone, do not add old context.
Understand semantic equivalents and paraphrases; do not rely on exact keyword matching.
Respond ONLY with strict JSON:
{"is_follow_up": true|false, "standalone_question": "<question>", "reason": "<short reason>"}."""


class FollowupDetector:
    @staticmethod
    def resolve(
        question: str,
        schema: DatabaseSchema,
        history: list[dict[str, Any]],
    ) -> str:
        shortcut_question = FollowupDetector._employee_shortcut(question, schema)
        if shortcut_question:
            logger.info("Resolved employee shortcut to: %s", shortcut_question)
            return shortcut_question

        name_field_question = FollowupDetector._employee_name_field_shortcut(question, schema)
        if name_field_question:
            logger.info("Resolved employee name field shortcut to: %s", name_field_question)
            return name_field_question

        if not history:
            vague_training_question = FollowupDetector._unresolved_training_program_shortcut(question)
            if vague_training_question:
                logger.info("Resolved vague training program question to: %s", vague_training_question)
                return vague_training_question
            return question

        user_prompt = (
            f"Schema:\n{schema.to_prompt_summary()}\n\n"
            f"Recent conversation:\n{FollowupDetector._format_history(history)}\n\n"
            f"Current question: {question}"
        )
        result = llm_service.complete_json(_SYSTEM_PROMPT, user_prompt)
        standalone = result.get("standalone_question", question)
        if not isinstance(standalone, str) or not standalone.strip():
            standalone = question

        vague_training_question = FollowupDetector._unresolved_training_program_shortcut(standalone)
        if vague_training_question:
            standalone = vague_training_question

        logger.info(
            "Follow-up resolution: %s -> %s (%s)",
            question,
            standalone,
            result.get("reason", ""),
        )
        return standalone.strip()

    @staticmethod
    def _employee_shortcut(question: str, schema: DatabaseSchema) -> str | None:
        match = _SHORTCUT_RE.match(question)
        if not match:
            return None

        empid_ref = FollowupDetector._find_column(schema, "empid")
        if not empid_ref:
            return None

        table_name, column_name = empid_ref
        return f"Show all information from {table_name} for employee with {column_name} {match.group(1)}."

    @staticmethod
    def _employee_name_field_shortcut(question: str, schema: DatabaseSchema) -> str | None:
        match = _NAME_FIELD_RE.match(question)
        if not match:
            return None

        first_name, last_name, requested_field = match.groups()
        if first_name.lower() in _NON_NAME_TERMS or last_name.lower() in _NON_NAME_TERMS:
            return None
        if not FollowupDetector._table_with_columns(schema, {"firstname", "lastname"}):
            return None
        if not FollowupDetector._field_exists(schema, requested_field):
            return None

        return f"Show {requested_field.strip()} for employee named {first_name.title()} {last_name.title()}."

    @staticmethod
    def _unresolved_training_program_shortcut(question: str) -> str | None:
        if not _VAGUE_TRAINING_PROGRAM_RE.search(question):
            return None

        normalized = question.lower()
        if "cost" not in normalized:
            return None

        return "Show the total training cost grouped by training program."

    @staticmethod
    def _find_column(schema: DatabaseSchema, column_name: str) -> tuple[str, str] | None:
        target = column_name.lower()
        for table in schema.tables.values():
            for column in table.columns:
                if column.name.lower() == target:
                    return table.name, column.name
        return None

    @staticmethod
    def _table_with_columns(schema: DatabaseSchema, column_names: set[str]) -> str | None:
        targets = {name.lower() for name in column_names}
        for table in schema.tables.values():
            table_columns = {column.name.lower() for column in table.columns}
            if targets.issubset(table_columns):
                return table.name
        return None

    @staticmethod
    def _field_exists(schema: DatabaseSchema, field_text: str) -> bool:
        requested_terms = FollowupDetector._terms(field_text)
        requested_compact = "".join(requested_terms)
        if not requested_compact:
            return False

        for table in schema.tables.values():
            for column in table.columns:
                column_terms = FollowupDetector._terms(column.name)
                column_compact = "".join(column_terms)
                if requested_compact == column_compact or requested_compact in column_compact:
                    return True
        return False

    @staticmethod
    def _terms(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower().replace("worklife", "work life"))


    @staticmethod
    def _format_history(history: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for index, item in enumerate(history[-5:], start=1):
            lines.append(f"Turn {index}:")
            lines.append(f"  User asked: {item.get('user', '')}")
            lines.append(f"  Standalone question used: {item.get('effective_question', item.get('user', ''))}")
            if item.get("generated_sql"):
                lines.append(f"  SQL used: {item['generated_sql']}")
            if item.get("tables_used"):
                lines.append(f"  Tables used: {item['tables_used']}")
            if item.get("result_preview"):
                lines.append(f"  Result preview: {item['result_preview']}")
            if item.get("assistant"):
                lines.append(f"  Assistant answered: {item['assistant']}")
        return "\n".join(lines)
