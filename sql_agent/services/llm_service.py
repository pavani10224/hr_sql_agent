"""
Single point of contact with the local LLM (Ollama).

Every agent node calls `LLMService.complete(...)` with a prompt built
purely from the dynamic schema summary + the user's question. No node
ever writes SQL itself or hands the model a hardcoded example query.
"""
from __future__ import annotations

import json
import re

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    def __init__(self) -> None:
        self._llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
        )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text completion for a system+user prompt pair."""
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = self._llm.invoke(messages)
        return (response.content or "").strip()

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Ask the model for strict JSON and parse it defensively.

        Local models occasionally wrap JSON in prose or code fences, so we
        extract the first {...} block before parsing rather than failing
        outright.
        """
        raw = self.complete(system_prompt, user_prompt)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        json_text = match.group(0) if match else raw
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning("Could not parse JSON from LLM output: %s", raw)
            return {}


llm_service = LLMService()
