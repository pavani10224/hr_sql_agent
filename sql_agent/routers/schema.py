from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from database.db_manager import db_manager
from database.schema_inspector import SchemaInspector
from schemas.response_schemas import SchemaResponse
from services.app_state import app_state
from utils.exceptions import NoDatabaseError, SchemaInspectionError

router = APIRouter(tags=["Schema"])


@router.get("/schema", response_model=SchemaResponse)
def get_schema() -> SchemaResponse:
    try:
        if app_state.schema is None:
            app_state.set_schema(SchemaInspector(db_manager.engine).inspect())
        schema = app_state.schema
    except (NoDatabaseError, SchemaInspectionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SchemaResponse(
        tables=schema.table_names(),
        schema_summary=schema.to_prompt_summary(),
        relationships=[asdict(r) for r in schema.relationships],
    )
