"""
Intent Understanding Node.

Classifies the free-form question into a short label purely for
observability / downstream table-selection hints. The label set is not
hardcoded to any domain -- the model is free to invent a label, we just
give a few illustrative examples.
"""
from __future__ import annotations

from services.llm_service import llm_service
from utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You classify the intent of a natural-language question that will be \
answered by querying a database. Respond ONLY with strict JSON: {"intent": "<short_label>"}. \
The label should be a short snake_case phrase describing the type of analysis \
(e.g. aggregation, comparison, lookup, trend_analysis, ranking, filtering). \
Infer the label from the question itself -- do not assume any particular domain."""


class IntentClassifier:
    @staticmethod
    def classify(question: str) -> str:
        result = llm_service.complete_json(_SYSTEM_PROMPT, f"Question: {question}")
        intent = result.get("intent", "unknown")
        logger.info("Classified intent: %s", intent)
        return intent
