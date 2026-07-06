"""
Converts an arbitrary set of uploaded CSV files into a single SQLite
database, inferring:

  * column data types (from pandas dtypes)
  * a primary key per table (first column that looks like an identifier
    and is unique, otherwise a surrogate "row_id")
  * foreign-key relationships BETWEEN tables, purely by:
        1. matching column names across tables (e.g. "emp_id" appears in
           both employee_engagement and training_and_development), and
        2. checking that a high proportion of the values in the
           "child" column actually exist in the candidate "parent" column.

No table/column names are ever hardcoded -- everything is derived from
whatever files are handed to `convert()`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config import settings
from models.schema_models import ForeignKeyInfo
from utils.exceptions import CSVConversionError
from utils.logger import get_logger

logger = get_logger(__name__)


class CSVToSQLiteConverter:
    """Builds (or rebuilds) the project's SQLite database from CSV files."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.sqlite_db_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def convert(self, csv_paths: list[Path]) -> dict[str, Any]:
        """Read every CSV, load it into its own table, discover relationships.

        Returns a summary dict used by the /upload endpoint response.
        """
        if not csv_paths:
            raise CSVConversionError("No CSV files were provided.")

        # Start from a clean database every time a new batch is uploaded.
        if self.db_path.exists():
            self.db_path.unlink()

        engine = create_engine(f"sqlite:///{self.db_path}")

        dataframes: dict[str, pd.DataFrame] = {}
        row_counts: dict[str, int] = {}

        for csv_path in csv_paths:
            table_name = self._sanitize_table_name(csv_path.stem)
            try:
                df = pd.read_csv(csv_path)
            except Exception as exc:  # noqa: BLE001
                raise CSVConversionError(f"Failed to read {csv_path.name}: {exc}") from exc

            df = self._clean_dataframe(df)
            dataframes[table_name] = df

            df.to_sql(table_name, engine, if_exists="replace", index=False)
            row_counts[table_name] = len(df)
            logger.info("Loaded table '%s' with %d rows, %d columns", table_name, len(df), len(df.columns))

        relationships = self._discover_relationships(dataframes)
        self._apply_primary_and_foreign_keys(engine, dataframes, relationships)

        return {
            "tables_created": list(dataframes.keys()),
            "total_rows": row_counts,
            "relationships_discovered": len(relationships),
            "relationships": relationships,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _sanitize_table_name(raw_name: str) -> str:
        safe = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in raw_name.strip().lower())
        if not safe or safe[0].isdigit():
            safe = f"t_{safe}"
        return safe

    @staticmethod
    def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names; let pandas' own dtype inference stand."""
        df.columns = [
            "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(col).strip().lower())
            for col in df.columns
        ]
        return df

    def _discover_relationships(
        self, dataframes: dict[str, pd.DataFrame]
    ) -> list[ForeignKeyInfo]:
        """Infer FK relationships by shared column names + value overlap.

        For every pair of tables (A, B) and every column name shared by
        both, treat the table with MORE distinct values in that column as
        the "parent" (the one owning that value as an identifier) and the
        other as the "child". A relationship is kept only if a high
        fraction of the child's non-null values are present in the
        parent's set of values.
        """
        relationships: list[ForeignKeyInfo] = []
        seen_pairs: set[tuple[str, str, str, str]] = set()
        table_names = list(dataframes.keys())

        def try_pair(table_a: str, col_a: str, table_b: str, col_b: str) -> None:
            df_a, df_b = dataframes[table_a], dataframes[table_b]
            values_a = set(df_a[col_a].dropna().unique())
            values_b = set(df_b[col_b].dropna().unique())
            if not values_a or not values_b:
                return

            # The parent is whichever side has more unique values (i.e. is
            # closer to being a primary key for that identifier).
            if len(values_a) >= len(values_b):
                parent_table, parent_col, parent_values = table_a, col_a, values_a
                child_table, child_col, child_values = table_b, col_b, values_b
            else:
                parent_table, parent_col, parent_values = table_b, col_b, values_b
                child_table, child_col, child_values = table_a, col_a, values_a

            pair_key = (child_table, child_col, parent_table, parent_col)
            if pair_key in seen_pairs:
                return

            overlap = len(child_values & parent_values) / len(child_values)
            if overlap >= settings.relationship_overlap_threshold:
                seen_pairs.add(pair_key)
                relationships.append(
                    ForeignKeyInfo(
                        from_table=child_table,
                        from_column=child_col,
                        to_table=parent_table,
                        to_column=parent_col,
                        confidence=round(overlap, 2),
                    )
                )
                logger.info(
                    "Discovered relationship: %s.%s -> %s.%s (overlap=%.2f)",
                    child_table, child_col, parent_table, parent_col, overlap,
                )

        for i, table_a in enumerate(table_names):
            for table_b in table_names[i + 1:]:
                df_a, df_b = dataframes[table_a], dataframes[table_b]

                # Pass 1: exact column-name matches (fast, high confidence).
                shared_columns = set(df_a.columns) & set(df_b.columns)
                for column in shared_columns:
                    try_pair(table_a, column, table_b, column)

                # Pass 2: identifier-like columns with DIFFERENT names
                # (e.g. "empid" vs "employee_id"). We only compare columns
                # that look like identifiers to keep the search space small
                # and avoid spuriously linking unrelated free-text columns.
                id_cols_a = [c for c in df_a.columns if self._looks_like_identifier(c)]
                id_cols_b = [c for c in df_b.columns if self._looks_like_identifier(c)]
                for col_a in id_cols_a:
                    for col_b in id_cols_b:
                        if col_a == col_b:
                            continue  # already handled in pass 1
                        try_pair(table_a, col_a, table_b, col_b)

        return relationships

    @staticmethod
    def _looks_like_identifier(column_name: str) -> bool:
        name = column_name.lower()
        return (
            name == "id"
            or name.endswith("_id")
            or name.endswith("id")
            or name.endswith("_code")
            or name.endswith("code")
            or name.endswith("_key")
        )

    def _apply_primary_and_foreign_keys(
        self,
        engine: Engine,
        dataframes: dict[str, pd.DataFrame],
        relationships: list[ForeignKeyInfo],
    ) -> None:
        """Rebuild each table with an explicit PRIMARY KEY and, where a
        relationship was discovered, an explicit FOREIGN KEY constraint,
        so that `PRAGMA foreign_key_list` can later report it natively.
        """
        # Group relationships by child table for convenient constraint building.
        fks_by_child: dict[str, list[ForeignKeyInfo]] = {}
        for rel in relationships:
            fks_by_child.setdefault(rel.from_table, []).append(rel)

        # Choose one primary key column per table: prefer a unique column
        # whose name suggests an identifier (ends with "id" or "_id" or is
        # exactly "id"); otherwise fall back to a surrogate key.
        primary_keys: dict[str, str] = {}
        for table, df in dataframes.items():
            candidate = None
            for col in df.columns:
                looks_like_id = col == "id" or col.endswith("_id") or col.endswith("id")
                if looks_like_id and df[col].is_unique and df[col].notna().all():
                    candidate = col
                    break
            primary_keys[table] = candidate or "__row_id__"

        with engine.begin() as conn:
            for table, df in dataframes.items():
                pk_col = primary_keys[table]
                needs_surrogate = pk_col == "__row_id__"
                work_df = df.copy()
                if needs_surrogate:
                    work_df.insert(0, "__row_id__", range(1, len(work_df) + 1))

                col_defs = []
                for col in work_df.columns:
                    sql_type = self._pandas_dtype_to_sql(work_df[col].dtype)
                    if col == pk_col:
                        col_defs.append(f'"{col}" {sql_type} PRIMARY KEY')
                    else:
                        col_defs.append(f'"{col}" {sql_type}')

                fk_defs = []
                for rel in fks_by_child.get(table, []):
                    fk_defs.append(
                        f'FOREIGN KEY ("{rel.from_column}") REFERENCES "{rel.to_table}"("{rel.to_column}")'
                    )

                all_defs = ", ".join(col_defs + fk_defs)
                conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table}"')
                conn.exec_driver_sql(f'CREATE TABLE "{table}" ({all_defs})')
                work_df.to_sql(table, conn, if_exists="append", index=False)

    @staticmethod
    def _pandas_dtype_to_sql(dtype) -> str:  # noqa: ANN001
        kind = dtype.kind
        if kind in ("i", "u"):
            return "INTEGER"
        if kind == "f":
            return "REAL"
        if kind == "b":
            return "BOOLEAN"
        if kind == "M":
            return "TIMESTAMP"
        return "TEXT"
