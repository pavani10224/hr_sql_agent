"""
Builds the LangGraph StateGraph implementing the full agent pipeline:

  schema_inspector -> intent_understanding -> relevance_checker
      -> (irrelevant) -> irrelevant_response -> END
      -> (relevant)   -> table_selection -> sql_generation -> sql_execution
            -> (success)          -> response_generator -> END
            -> (fail, can retry)  -> sql_generation (loop, with error context)
            -> (fail, exhausted)  -> failure_response -> END
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents.intent_classifier import IntentClassifier
from agents.relevance_checker import RelevanceChecker
from agents.response_generator import ResponseGenerator
from agents.sql_generator import SQLGenerator
from agents.table_selector import TableSelector
from agents.validator import SQLValidator
from config import settings
from database.db_manager import db_manager
from database.schema_inspector import SchemaInspector
from graph.state import AgentState
from services.app_state import app_state
from utils.logger import get_logger

logger = get_logger(__name__)


# ----------------------------------------------------------------------
# Node implementations
# ----------------------------------------------------------------------
def schema_inspector_node(state: AgentState) -> AgentState:
    schema = SchemaInspector(db_manager.engine).inspect()
    app_state.set_schema(schema)
    return {**state, "schema": schema, "schema_summary": schema.to_prompt_summary()}


def intent_understanding_node(state: AgentState) -> AgentState:
    intent = IntentClassifier.classify(state["question"])
    return {**state, "intent": intent}


def relevance_checker_node(state: AgentState) -> AgentState:
    is_relevant, reason = RelevanceChecker.check(state["question"], state["schema_summary"])
    return {**state, "is_relevant": is_relevant, "relevance_reason": reason}


def irrelevant_response_node(state: AgentState) -> AgentState:
    answer = ResponseGenerator.friendly_irrelevant_response(
        state.get("original_question", state["question"]), state.get("relevance_reason", "")
    )
    return {**state, "final_answer": answer, "generated_sql": None, "selected_tables": []}


def table_selection_node(state: AgentState) -> AgentState:
    tables = TableSelector.select(state["question"], state["schema"])
    return {**state, "selected_tables": tables}


def sql_generation_node(state: AgentState) -> AgentState:
    sql = SQLGenerator.generate(
        question=state["question"],
        schema=state["schema"],
        selected_tables=state["selected_tables"],
        previous_sql=state.get("generated_sql"),
        previous_error=state.get("sql_error"),
    )
    return {**state, "generated_sql": sql}


def sql_execution_node(state: AgentState) -> AgentState:
    result = SQLValidator.execute_and_validate(state["generated_sql"] or "")
    updated: AgentState = {
        **state,
        "generated_sql": result["sql"],
        "sql_rows": result["rows"],
        "execution_time_ms": result["elapsed_ms"],
        "sql_error": result["error"],
    }
    if result["error"] is not None:
        updated["retry_count"] = state.get("retry_count", 0) + 1
    return updated


def response_generator_node(state: AgentState) -> AgentState:
    display_question = state.get("original_question", state["question"])
    answer = ResponseGenerator.generate(display_question, state.get("sql_rows", []))
    app_state.record_query(display_question, state.get("generated_sql"), state.get("selected_tables", []))
    return {**state, "final_answer": answer}


def failure_response_node(state: AgentState) -> AgentState:
    display_question = state.get("original_question", state["question"])
    answer = ResponseGenerator.friendly_failure_response(display_question)
    app_state.record_query(display_question, state.get("generated_sql"), state.get("selected_tables", []))
    return {**state, "final_answer": answer}


# ----------------------------------------------------------------------
# Conditional routing
# ----------------------------------------------------------------------
def route_after_relevance(state: AgentState) -> str:
    return "table_selection" if state.get("is_relevant") else "irrelevant_response"


def route_after_execution(state: AgentState) -> str:
    if state.get("sql_error") is None:
        return "response_generator"
    if state.get("retry_count", 0) < settings.max_sql_retries:
        return "sql_generation"
    return "failure_response"


# ----------------------------------------------------------------------
# Graph assembly
# ----------------------------------------------------------------------
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("schema_inspector", schema_inspector_node)
    graph.add_node("intent_understanding", intent_understanding_node)
    graph.add_node("relevance_checker", relevance_checker_node)
    graph.add_node("irrelevant_response", irrelevant_response_node)
    graph.add_node("table_selection", table_selection_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("sql_execution", sql_execution_node)
    graph.add_node("response_generator", response_generator_node)
    graph.add_node("failure_response", failure_response_node)

    graph.set_entry_point("schema_inspector")
    graph.add_edge("schema_inspector", "intent_understanding")
    graph.add_edge("intent_understanding", "relevance_checker")

    graph.add_conditional_edges(
        "relevance_checker",
        route_after_relevance,
        {"table_selection": "table_selection", "irrelevant_response": "irrelevant_response"},
    )
    graph.add_edge("irrelevant_response", END)

    graph.add_edge("table_selection", "sql_generation")
    graph.add_edge("sql_generation", "sql_execution")

    graph.add_conditional_edges(
        "sql_execution",
        route_after_execution,
        {
            "response_generator": "response_generator",
            "sql_generation": "sql_generation",
            "failure_response": "failure_response",
        },
    )
    graph.add_edge("response_generator", END)
    graph.add_edge("failure_response", END)

    return graph.compile()


compiled_graph = build_graph()
