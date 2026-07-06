"""
Plain domain objects that represent whatever database happens to be loaded.

Nothing in this file references a concrete table or column name -- these
are generic containers populated at runtime by database/schema_inspector.py
and database/csv_to_sqlite.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnInfo:
    name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True


@dataclass
class ForeignKeyInfo:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    confidence: float = 1.0  # 1.0 = declared FK, <1.0 = statistically inferred


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


@dataclass
class DatabaseSchema:
    tables: dict[str, TableInfo] = field(default_factory=dict)
    relationships: list[ForeignKeyInfo] = field(default_factory=list)

    def table_names(self) -> list[str]:
        return list(self.tables.keys())

    def to_prompt_summary(self) -> str:
        """Render the schema as compact, LLM-friendly text.

        This is the ONLY view of the database the LLM ever receives --
        it never sees raw CSVs or hardcoded business terms.
        """
        lines: list[str] = []
        for table in self.tables.values():
            col_desc = ", ".join(
                f"{c.name} ({c.data_type}{', PK' if c.is_primary_key else ''})"
                for c in table.columns
            )
            lines.append(f"Table: {table.name} [{table.row_count} rows]")
            lines.append(f"  Columns: {col_desc}")
            if table.sample_rows:
                lines.append(f"  Sample row: {table.sample_rows[0]}")
            lines.append("")

        if self.relationships:
            lines.append("Discovered Relationships:")
            for rel in self.relationships:
                tag = "declared FK" if rel.confidence >= 1.0 else f"inferred, confidence={rel.confidence:.2f}"
                lines.append(
                    f"  {rel.from_table}.{rel.from_column} -> "
                    f"{rel.to_table}.{rel.to_column} ({tag})"
                )
        else:
            lines.append("Discovered Relationships: none found")

        return "\n".join(lines)
