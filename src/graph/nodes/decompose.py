"""Decompose node — splits the standalone question into atomic tasks per L4.

Always returns `list[TaskState]`:
  - single-task query  → `[task]`
  - compound query     → `[task1, task2, ...]`

Cuttable (Risk #4): `features.decomposition_enabled: false` forces
`[standalone_question]` with no LLM call.

Backend selector:
  - backend=fake → single-task default (matches Phase-A behavior).
  - backend=openrouter → real LLM call with structured output.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config import settings
from src.graph.client import get_llm
from src.graph.logging import timed
from src.graph.prompts import render_pair
from src.graph.state import OuterState, TaskState, initial_task_state


class Decomposition(BaseModel):
    """Structured output for L4 decomposition."""

    tasks: list[str] = Field(
        description=(
            "Atomic, self-contained task questions. Use a single-element list "
            "with the original request unchanged when the request is not compound."
        )
    )


@timed("decompose")
async def decompose_node(state: OuterState) -> dict:
    standalone = state.get("standalone_question") or state["user_query"]
    grade = state["grade"]
    subject = state["subject"]
    language = state.get("language", "en")

    if not settings.features.decomposition_enabled:
        questions: list[str] = [standalone]
    elif settings.llm.backend == "fake":
        questions = [standalone]
    else:
        llm = get_llm(temperature=settings.llm.classifier_temperature)
        structured = llm.with_structured_output(Decomposition)
        system, user = render_pair("decompose.j2", question=standalone)
        decision: Decomposition = await structured.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        questions = [q.strip() for q in decision.tasks if q.strip()] or [standalone]

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
