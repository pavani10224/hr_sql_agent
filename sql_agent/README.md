# Dynamic AI SQL Agent

An autonomous LangGraph agent that turns a folder of CSV files into a queryable
SQLite database and answers natural-language questions about it -- with **no
hardcoded table names, columns, joins, or SQL**. Point it at a different set of
CSVs (or a different SQLite DB entirely) and it re-discovers everything at
runtime.

## How it stays fully dynamic

| Concern | How it's handled |
|---|---|
| Table/column names | Read from `sqlite_master` + `PRAGMA table_info()` at query time |
| Relationships / joins | Discovered by matching shared column names across tables and checking value overlap (`database/csv_to_sqlite.py::_discover_relationships`); confirmed relationships are written as real `FOREIGN KEY` constraints, so `PRAGMA foreign_key_list()` reports them natively |
| SQL | Generated per-question by the LLM from the schema summary alone (`agents/sql_generator.py`) |
| Business logic | None baked in -- intent labels, relevance checks, and answers are all model-driven |

## Architecture

```
main.py                     FastAPI app assembly
routers/                    HTTP layer (upload, ask, schema, health)
graph/
  state.py                  LangGraph AgentState
  workflow.py                Node wiring + conditional retry/relevance routing
agents/                     One module per graph node (intent, relevance,
                             table selection, SQL generation, validation, response)
database/
  csv_to_sqlite.py           CSV -> SQLite + relationship discovery
  schema_inspector.py        sqlite_master / PRAGMA introspection
  db_manager.py               Engine lifecycle + read-only query execution
services/
  llm_service.py              Ollama wrapper (chat + strict-JSON completions)
  query_executor.py           SQL cleanup (strips markdown fences, etc.)
  app_state.py                 In-memory cache of current schema / last query
models/schema_models.py     DatabaseSchema / TableInfo / ForeignKeyInfo dataclasses
schemas/                    Pydantic request/response models
utils/                      Logger + exception hierarchy
```

### Agent graph

```
schema_inspector -> intent_understanding -> relevance_checker
    ├─ irrelevant -> irrelevant_response -> END
    └─ relevant   -> table_selection -> sql_generation -> sql_execution
                          ├─ success        -> response_generator -> END
                          ├─ fail, retries left -> sql_generation (loop, with error)
                          └─ fail, exhausted -> failure_response -> END
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Pull a local model once, e.g.:
ollama pull llama3.1

cp .env.example .env   # adjust model name / thresholds if needed
uvicorn main:app --reload
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service + database readiness check |
| POST | `/upload` | Upload one or more CSVs (multipart `files[]`); rebuilds the SQLite DB |
| GET | `/schema` | Current discovered schema + relationships |
| POST | `/ask` | `{"question": "..."}` -> full agent response |
| GET | `/generated_sql` | SQL generated for the most recent question |

### Example

```bash
curl -F "files=@employee_data.csv" -F "files=@employee_engagement.csv" \
     -F "files=@training_and_development.csv" http://localhost:8000/upload

curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What is the average engagement score by department?"}'
```

Response shape:

```json
{
  "question": "What is the average engagement score by department?",
  "intent": "aggregation",
  "is_relevant": true,
  "generated_sql": "SELECT ... FROM employee_data JOIN employee_engagement ON ...",
  "tables_used": ["employee_data", "employee_engagement"],
  "execution_time_ms": 4.2,
  "row_count": 6,
  "answer": "The average engagement score ranges from ...",
  "retries": 0,
  "error": null
}
```

## Trying it with a different database

Nothing here assumes HR data. Upload any set of related CSVs (e.g. orders /
customers / products with shared `customer_id` / `product_id` columns) and
the same pipeline discovers the new schema and relationships with zero code
changes.

## Notes / limitations

- Only read-only `SELECT`/`WITH` statements are ever executed (`db_manager.py`
  rejects anything else, including PRAGMA/DDL/DML from generated SQL).
- Relationship discovery is heuristic (name match + value-overlap ratio,
  tunable via `SQLAGENT_RELATIONSHIP_OVERLAP_THRESHOLD`); very sparse or
  oddly-named keys may not be discovered automatically.
- Uploading a new batch of CSVs replaces the previous database file.
