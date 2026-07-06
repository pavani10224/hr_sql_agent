from typing import Any, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    database_ready: bool
    ollama_model: str


class UploadResponse(BaseModel):
    message: str
    tables_created: list[str]
    total_rows: dict[str, int]
    relationships_discovered: int


class SchemaResponse(BaseModel):
    tables: list[str]
    schema_summary: str
    relationships: list[dict[str, Any]]


class AskResponse(BaseModel):
    question: str
    answer: str

    generated_sql: Optional[str] = None

    tables_used: list[str] = []

    query_result: list[dict[str, Any]] = []

    business_summary: Optional[str] = None

    error: Optional[str] = None


class GeneratedSQLResponse(BaseModel):
    question: str
    generated_sql: Optional[str]
    tables_used: list[str]
