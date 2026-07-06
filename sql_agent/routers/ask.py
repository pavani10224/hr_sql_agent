from fastapi import APIRouter, HTTPException

from agents.followup_detector import FollowupDetector
from database.db_manager import db_manager
from database.schema_inspector import SchemaInspector
from graph.workflow import compiled_graph
from schemas.request_schemas import AskRequest
from schemas.response_schemas import AskResponse, GeneratedSQLResponse
from services.app_state import app_state
from utils.exceptions import NoDatabaseError
from utils.logger import get_logger
from services.conversation_memory import conversation_memory

logger = get_logger(__name__)
router = APIRouter(tags=["Ask"])


@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest) -> AskResponse:
    if not db_manager.is_ready():
        raise HTTPException(status_code=404, detail="No database found. Upload CSV files first via /upload.")

    schema = app_state.schema or SchemaInspector(db_manager.engine).inspect()
    app_state.set_schema(schema)
    effective_question = FollowupDetector.resolve(
        request.question,
        schema,
        conversation_memory.get_history(),
    )
    initial_state = {
        "question": effective_question,
        "original_question": request.question,
        "retry_count": 0,
    }

    try:
        result = compiled_graph.invoke(initial_state)
    except NoDatabaseError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error while running agent graph")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc
  
    conversation_memory.add(
        user_question=request.question,
        effective_question=effective_question,
        assistant_answer=result.get("final_answer", ""),
        generated_sql=result.get("generated_sql"),
        tables_used=result.get("selected_tables", []),
        result_rows=result.get("sql_rows", []),
    )
    return AskResponse(
    question=request.question,

    answer=result.get("final_answer", ""),

    generated_sql=result.get("generated_sql"),

    tables_used=result.get("selected_tables", []),

    query_result=result.get("sql_rows", []),

    business_summary=result.get("business_summary"),

    error=result.get("sql_error"),
)
from pydantic import BaseModel


class ExecuteSQLRequest(BaseModel):
    sql: str


@router.post("/execute_sql")
def execute_sql(request: ExecuteSQLRequest):

    try:

        rows, _ = db_manager.execute_query(request.sql)

        return {
            "query_result": rows
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.get("/generated_sql", response_model=GeneratedSQLResponse)
def get_last_generated_sql() -> GeneratedSQLResponse:
    if app_state.last_question is None:
        raise HTTPException(status_code=404, detail="No question has been asked yet.")
    return GeneratedSQLResponse(
        question=app_state.last_question,
        generated_sql=app_state.last_sql,
        tables_used=app_state.last_tables_used,
    )
