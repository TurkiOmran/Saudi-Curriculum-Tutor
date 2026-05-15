"""Decompose node — splits the standalone question into atomic tasks per L4.

Phase A stub: always returns `[standalone_question]` (single task). Phase C
swaps in a structured-output LLM call.

Bypassed entirely (no LLM) when `features.decomposition_enabled: false` —
the Risk #4 escape hatch.
"""

from __future__ import annotations

from src.config import settings
from src.graph.state import OuterState, TaskState, initial_task_state


async def decompose_node(state: OuterState) -> dict:
    standalone = state.get("standalone_question") or state["user_query"]
    grade = state["grade"]
    subject = state["subject"]
    language = state.get("language", "en")

    if not settings.features.decomposition_enabled:
        # Cuttable per L4 — no LLM call, single task.
        questions: list[str] = [standalone]
    else:
        # Phase A: stub returns the single-task default.
        # Phase C: real LLM call with structured output.
        questions = [standalone]

    tasks: list[TaskState] = [
        initial_task_state(
            grade=grade,
            subject=subject,
            standalone_question=q,
            language=language,
        )
        for q in questions
    ]
    return {"tasks": tasks}
