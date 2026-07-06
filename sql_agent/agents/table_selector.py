"""
Table Selection Node.

Given the full schema summary and the question, the model picks only the
tables it needs. This keeps the SQL Generation prompt small and reduces
the chance the model hallucinates joins against irrelevant tables.
"""
from __future__ import annotations

import re

from models.schema_models import DatabaseSchema
from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA_HINT_STOP_TERMS = {
    "all",
    "data",
    "detail",
    "details",
    "display",
    "employee",
    "employees",
    "give",
    "id",
    "info",
    "information",
    "score",
    "show",
    "what",
}

_SYSTEM_PROMPT = """You select which tables, from the schema below, are needed to answer the \
question. Respond ONLY with strict JSON: {"tables": ["table1", "table2"]}. \
Include a table if it is directly needed OR if it is needed as a join bridge to connect \
other required tables via the discovered relationships. Understand paraphrases, synonyms, \
spacing differences, and hyphenation in the question. Do not include unrelated tables."""


class TableSelector:
    @staticmethod
    def select(question: str, schema: DatabaseSchema) -> list[str]:
        user_prompt = f"Schema:\n{schema.to_prompt_summary()}\n\nQuestion: {question}"
        result = llm_service.complete_json(_SYSTEM_PROMPT, user_prompt)
        tables = result.get("tables", [])

        valid_tables = [t for t in tables if t in schema.tables]
        if not valid_tables:
            # Fall back to every table rather than failing outright --
            # the SQL generator will still only use what it needs.
            logger.warning("Table selector returned no valid tables; falling back to all tables.")
            valid_tables = schema.table_names()

        valid_tables = TableSelector._add_schema_hint_tables(question, schema, valid_tables)

        logger.info("Selected tables: %s", valid_tables)
        return valid_tables

    @staticmethod
    def _add_schema_hint_tables(
        question: str,
        schema: DatabaseSchema,
        selected_tables: list[str],
    ) -> list[str]:
        """Keep tables in scope when the question clearly names their columns.

        The LLM still makes the semantic table-selection decision. This small
        safety net handles compact user wording such as "worklife" for a column
        named "work_life_balance_score" so join prompts do not lose a table.
        """
        selected = list(dict.fromkeys(selected_tables))
        question_terms = TableSelector._terms(question)
        question_compact = "".join(question_terms)
        asks_for_named_employee = "employee" in question_terms and "named" in question_terms

        for table in schema.tables.values():
            if table.name in selected:
                continue
            table_columns = {column.name.lower() for column in table.columns}
            if asks_for_named_employee and {"firstname", "lastname"}.issubset(table_columns):
                selected.append(table.name)
                continue
            for column in table.columns:
                column_terms = TableSelector._terms(column.name)
                column_compact = "".join(column_terms)
                meaningful_column_terms = TableSelector._meaningful_terms(column_terms)
                meaningful_question_terms = TableSelector._meaningful_terms(question_terms)

                if (
                    column_compact in question_compact
                    or bool(meaningful_column_terms & meaningful_question_terms)
                ):
                    selected.append(table.name)
                    break

        return selected

    @staticmethod
    def _terms(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower().replace("worklife", "work life"))

    @staticmethod
    def _meaningful_terms(terms: list[str]) -> set[str]:
        return {
            term
            for term in terms
            if len(term) > 3 and term not in _SCHEMA_HINT_STOP_TERMS
        }
