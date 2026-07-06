from fastapi import APIRouter

from config import settings
from database.db_manager import db_manager
from schemas.response_schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        database_ready=db_manager.is_ready(),
        ollama_model=settings.ollama_model,
    )
