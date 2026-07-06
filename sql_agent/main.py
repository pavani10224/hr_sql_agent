"""
Dynamic AI SQL Agent -- FastAPI entrypoint.

Wires together the upload / ask / schema / health routers. All agent
intelligence lives in graph/ and agents/; this file only assembles the
HTTP layer.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import ask, health, schema, upload
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "An autonomous AI agent that dynamically inspects any uploaded SQLite "
        "database (built from CSVs), discovers table relationships, and answers "
        "natural language questions by generating and validating SQL on the fly."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(ask.router)
app.include_router(schema.router)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("%s v%s starting up.", settings.app_name, settings.app_version)
    logger.info("Using Ollama model '%s' at %s", settings.ollama_model, settings.ollama_base_url)
    if settings.sqlite_db_path.exists():
        logger.info("Existing database found at %s", settings.sqlite_db_path)
    else:
        logger.info("No database yet -- POST CSV files to /upload to get started.")
