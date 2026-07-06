import sqlite3
from pathlib import Path

from sqlalchemy import create_engine

from database.schema_inspector import SchemaInspector


def test_inspector_infers_relationships_from_shared_ids(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE orders (id INTEGER, total REAL)")
        conn.execute("INSERT INTO customers (id, name) VALUES (1, 'Alice')")
        conn.execute("INSERT INTO orders (id, total) VALUES (1, 25.5)")
        conn.commit()
    finally:
        conn.close()

    engine = create_engine(f"sqlite:///{db_path}")
    schema = SchemaInspector(engine).inspect()

    assert any(
        relationship.from_table == "orders"
        and relationship.to_table == "customers"
        and relationship.from_column == "id"
        and relationship.to_column == "id"
        for relationship in schema.relationships
    )
