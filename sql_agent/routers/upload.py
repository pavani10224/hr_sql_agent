from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from config import settings
from database.csv_to_sqlite import CSVToSQLiteConverter
from database.db_manager import db_manager
from database.schema_inspector import SchemaInspector
from schemas.response_schemas import UploadResponse
from services.app_state import app_state
from services.conversation_memory import conversation_memory
from utils.exceptions import CSVConversionError
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Upload"])


@router.post("/upload", response_model=UploadResponse)
async def upload_csvs(files: list[UploadFile]) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="At least one CSV file is required.")

    saved_paths: list[Path] = []
    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"'{upload.filename}' is not a .csv file.")
        destination = settings.upload_dir / upload.filename
        content = await upload.read()
        destination.write_bytes(content)
        saved_paths.append(destination)

    try:
        converter = CSVToSQLiteConverter()
        summary = converter.convert(saved_paths)
    except CSVConversionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Force the db manager to reopen the freshly-written .db file, then
    # cache the inspected schema for the /schema endpoint.
    db_manager.refresh()
    schema = SchemaInspector(db_manager.engine).inspect()
    app_state.set_schema(schema)
    conversation_memory.clear()

    return UploadResponse(
        message=f"Successfully built database from {len(saved_paths)} CSV file(s).",
        tables_created=summary["tables_created"],
        total_rows=summary["total_rows"],
        relationships_discovered=summary["relationships_discovered"],
    )
