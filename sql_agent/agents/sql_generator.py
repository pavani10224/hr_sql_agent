"""
SQL Generation Node.

The model receives ONLY:
    - the question
    - the schema summary, restricted to the tables Table Selection chose
    - the discovered relationships relevant to those tables
    - (on retry) the previous SQL and the error it produced

It must produce a single read-only SQLite SELECT statement. No template,
no hardcoded join, no hardcoded column reference is ever injected here.
"""
from __future__ import annotations

from models.schema_models import DatabaseSchema
from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are a SQLite expert. Generate exactly one read-only SQL SELECT \
statement that answers the user's question, using only the tables and columns given below. \
Rules:
- Use only SQLite-compatible syntax.
- Use only the tables/columns provided -- never invent a name.
- Understand semantic equivalents, paraphrases, spacing, and hyphenation in the user's wording.
- If the question asks to show all information/details for a row or entity, select all columns
  from the matching table with SELECT * unless the user asks for specific fields.
- Never use vague words like this, that, current, previous, selected, or mentioned as literal
  filter values. If a specific value was not resolved in the question, answer at the natural
  grouped level. For example, for a training program total cost with no program name, group by
  training_program_name and sum training_cost.
- If tables must be joined, use the discovered relationships provided; infer the correct \
  join columns yourself, do not assume a join exists unless the relationship section shows it.
- Never write INSERT, UPDATE, DELETE, DROP, ALTER, or any statement other than SELECT.
- Respond ONLY with strict JSON: {"sql": "<the SQL statement>"}. No markdown, no commentary."""


class SQLGenerator:
    @staticmethod
    def generate(
        question: str,
        schema: DatabaseSchema,
        selected_tables: list[str],
        previous_sql: str | None = None,
        previous_error: str | None = None,
    ) -> str:
        restricted_summary = SQLGenerator._restricted_summary(schema, selected_tables)

        user_prompt = f"Schema (relevant tables only):\n{restricted_summary}\n\nQuestion: {question}"
        if previous_sql and previous_error:
            user_prompt += (
                f"\n\nA previous attempt failed.\nPrevious SQL: {previous_sql}\n"
                f"Error: {previous_error}\nFix the SQL to resolve this error."
            )

        result = llm_service.complete_json(_SYSTEM_PROMPT, user_prompt)
        sql = result.get("sql", "").strip()
        logger.info("Generated SQL: %s", sql)
        return sql

    @staticmethod
    def _restricted_summary(schema: DatabaseSchema, selected_tables: list[str]) -> str:
        selected_set = set(selected_tables)
        lines = []
        for name, table in schema.tables.items():
            if name not in selected_set:
                continue
            col_desc = ", ".join(f"{c.name} ({c.data_type})" for c in table.columns)
            lines.append(f"Table: {table.name}\n  Columns: {col_desc}")

        relevant_rels = [
            r for r in schema.relationships
            if r.from_table in selected_set and r.to_table in selected_set
        ]
        if relevant_rels:
            lines.append("Relationships:")
            for r in relevant_rels:
                lines.append(f"  {r.from_table}.{r.from_column} -> {r.to_table}.{r.to_column}")

        return "\n".join(lines)
