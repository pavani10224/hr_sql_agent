"""
Standalone converter: turn a folder of CSVs into a single SQLite .db file,
without starting the FastAPI server. Useful when you just need the .db
artifact itself (e.g. to submit for a project, or inspect in DB Browser
for SQLite).

Usage:
    python scripts/csv_to_db.py path/to/csv_folder
    python scripts/csv_to_db.py file1.csv file2.csv file3.csv
    python scripts/csv_to_db.py path/to/csv_folder --out my_database.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.csv_to_sqlite import CSVToSQLiteConverter  # noqa: E402


def collect_csv_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.csv")))
        elif p.is_file() and p.suffix.lower() == ".csv":
            paths.append(p)
        else:
            print(f"Skipping '{item}' (not a .csv file or directory of CSVs)")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert CSV files into a single SQLite .db file.")
    parser.add_argument("inputs", nargs="+", help="CSV file(s) and/or a folder containing CSVs")
    parser.add_argument("--out", default="data/hr_dynamic.db", help="Output .db path (default: data/hr_dynamic.db)")
    args = parser.parse_args()

    csv_paths = collect_csv_paths(args.inputs)
    if not csv_paths:
        print("No CSV files found.")
        sys.exit(1)

    print(f"Found {len(csv_paths)} CSV file(s): {[p.name for p in csv_paths]}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    converter = CSVToSQLiteConverter(db_path=out_path)
    summary = converter.convert(csv_paths)

    print()
    print(f"Database written to: {out_path.resolve()}")
    print(f"Tables created:      {summary['tables_created']}")
    print(f"Row counts:          {summary['total_rows']}")
    print(f"Relationships found: {summary['relationships_discovered']}")


if __name__ == "__main__":
    main()
