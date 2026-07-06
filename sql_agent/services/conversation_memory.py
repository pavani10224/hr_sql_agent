from collections import deque
from typing import Any

class ConversationMemory:

    def __init__(self, max_history: int = 10):
        self.history = deque(maxlen=max_history)

    def add(
        self,
        user_question: str,
        assistant_answer: str,
        effective_question: str | None = None,
        generated_sql: str | None = None,
        tables_used: list[str] | None = None,
        result_rows: list[dict[str, Any]] | None = None,
    ):
        self.history.append({
            "user": user_question,
            "effective_question": effective_question or user_question,
            "assistant": assistant_answer
        })
        entry = self.history[-1]
        if generated_sql:
            entry["generated_sql"] = generated_sql
        if tables_used:
            entry["tables_used"] = tables_used
        if result_rows:
            entry["result_preview"] = result_rows[:5]

    def get_history(self):
        return list(self.history)

    def clear(self):
        self.history.clear()


conversation_memory = ConversationMemory()
