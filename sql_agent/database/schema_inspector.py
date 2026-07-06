"""
Dynamically inspects whatever SQLite database is currently loaded.

Uses only generic introspection primitives:
    - sqlite_master            -> list of tables
    - PRAGMA table_info()      -> columns, types, PK flags
    - PRAGMA foreign_key_list()-> declared relationships
    - SELECT * ... LIMIT n     -> sample rows

This is the ONLY module that talks to sqlite_master / PRAGMA; everything
downstream (agents, LLM prompts) consumes the resulting DatabaseSchema
object, never raw SQL metadata.
"""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config import settings
from models.schema_models import ColumnInfo, DatabaseSchema, ForeignKeyInfo, TableInfo
from utils.exceptions import SchemaInspectionError
from utils.logger import get_logger

logger = get_logger(__name__)


class SchemaInspector:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def inspect(self) -> DatabaseSchema:
        try:
            with self.engine.connect() as conn:
                table_names = self._list_tables(conn)
                tables: dict[str, TableInfo] = {}

                for table_name in table_names:
                    tables[table_name] = self._inspect_table(conn, table_name)

                relationships: list[ForeignKeyInfo] = []
                for table_name in table_names:
                    relationships.extend(self._inspect_foreign_keys(conn, table_name))
                relationships.extend(self._infer_relationships(tables))

            deduped_relationships = self._dedupe_relationships(relationships)
            return DatabaseSchema(tables=tables, relationships=deduped_relationships)
        except SchemaInspectionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SchemaInspectionError(f"Failed to inspect database: {exc}") from exc

    # ------------------------------------------------------------------
    @staticmethod
    def _list_tables(conn) -> list[str]:  # noqa: ANN001
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        ).fetchall()
        return [row[0] for row in rows]

    def _inspect_table(self, conn, table_name: str) -> TableInfo:  # noqa: ANN001
        pragma_rows = conn.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
        columns: list[ColumnInfo] = []
        primary_keys: list[str] = []

        for row in pragma_rows:
            # row: (cid, name, type, notnull, dflt_value, pk)
            _, name, col_type, notnull, _, pk = row
            is_pk = bool(pk)
            if is_pk:
                primary_keys.append(name)
            columns.append(
                ColumnInfo(
                    name=name,
                    data_type=col_type or "TEXT",
                    is_primary_key=is_pk,
                    is_nullable=not bool(notnull),
                )
            )

        row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar() or 0

        sample_rows = []
        sample_result = conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT {settings.max_sample_rows}'))
        sample_columns = list(sample_result.keys())
        for row in sample_result.fetchall():
            sample_rows.append(dict(zip(sample_columns, row)))

        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            sample_rows=sample_rows,
            row_count=row_count,
        )

    @staticmethod
    def _inspect_foreign_keys(conn, table_name: str) -> list[ForeignKeyInfo]:  # noqa: ANN001
        rows = conn.execute(text(f'PRAGMA foreign_key_list("{table_name}")')).fetchall()
        relationships = []
        for row in rows:
            # row: (id, seq, table, from, to, on_update, on_delete, match)
            _, _, ref_table, from_col, to_col, *_ = row
            relationships.append(
                ForeignKeyInfo(
                    from_table=table_name,
                    from_column=from_col,
                    to_table=ref_table,
                    to_column=to_col,
                    confidence=1.0,
                )
            )
        return relationships

    def _infer_relationships(self, tables: dict[str, TableInfo]) -> list[ForeignKeyInfo]:
        relationships: list[ForeignKeyInfo] = []
        table_names = list(tables.keys())

        for from_table_name in table_names:
            from_table = tables[from_table_name]
            for from_column in from_table.columns:
                if from_column.is_primary_key:
                    continue
                if not self._looks_like_foreign_key(from_column.name):
                    continue

                for to_table_name in table_names:
                    if to_table_name == from_table_name:
                        continue

                    to_table = tables[to_table_name]
                    for to_column in to_table.columns:
                        if not to_column.is_primary_key and not self._looks_like_foreign_key(to_column.name):
                            continue
                        if not self._identifier_names_match(from_column.name, to_column.name):
                            continue

                        overlap_ratio = self._value_overlap_ratio(
                            from_table,
                            from_column.name,
                            to_table,
                            to_column.name,
                        )
                        if overlap_ratio < settings.relationship_overlap_threshold:
                            continue

                        relationships.append(
                            ForeignKeyInfo(
                                from_table=from_table_name,
                                from_column=from_column.name,
                                to_table=to_table_name,
                                to_column=to_column.name,
                                confidence=0.8,
                            )
                        )
                        break
                    else:
                        continue
                    break

        return relationships

    @staticmethod
    def _dedupe_relationships(relationships: list[ForeignKeyInfo]) -> list[ForeignKeyInfo]:
        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[ForeignKeyInfo] = []
        for relationship in relationships:
            key = (
                relationship.from_table,
                relationship.from_column,
                relationship.to_table,
                relationship.to_column,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(relationship)
        return deduped

    @staticmethod
    def _looks_like_foreign_key(column_name: str) -> bool:
        normalized = column_name.lower()
        return normalized.endswith("_id") or normalized == "id" or normalized.endswith("id")

    @staticmethod
    def _identifier_names_match(left_name: str, right_name: str) -> bool:
        left_norm = SchemaInspector._normalize_identifier(left_name)
        right_norm = SchemaInspector._normalize_identifier(right_name)

        if left_norm == right_norm:
            return True
        if left_norm == "id" and right_norm.endswith("_id"):
            return True
        if right_norm == "id" and left_norm.endswith("_id"):
            return True
        return False

    @staticmethod
    def _normalize_identifier(name: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        aliases = {
            "empid": "employee_id",
            "employeeid": "employee_id",
            "emp_id": "employee_id",
            "userid": "user_id",
            "customerid": "customer_id",
        }
        return aliases.get(normalized, normalized)

    @staticmethod
    def _value_overlap_ratio(
        left_table: TableInfo,
        left_column: str,
        right_table: TableInfo,
        right_column: str,
    ) -> float:
        left_values = {
            row.get(left_column)
            for row in left_table.sample_rows
            if row.get(left_column) is not None
        }
        right_values = {
            row.get(right_column)
            for row in right_table.sample_rows
            if row.get(right_column) is not None
        }

        if not left_values or not right_values:
            return 0.0

        overlap = len(left_values & right_values)
        return overlap / min(len(left_values), len(right_values))
