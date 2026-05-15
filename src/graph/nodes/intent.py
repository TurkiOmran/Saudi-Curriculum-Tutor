"""Intent node — classifies the request into one of 5 intents per L13.

Backend selector:
  - backend=fake → returns "qa" (the Phase-A canned value, so the no-API-key
    smoke run still works).
  - backend=openrouter → real LLM call with structured output
    (`llm.with_structured_output(IntentDecision)`).

`teacher-support` was dropped (L12). Five intents only:
qa / explain / summarize / revise / quiz.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config import settings
from src.graph.client import get_llm
from src.graph.logging import timed
from src.graph.prompts import render_pair
from src.graph.state import TaskState


class IntentDecision(BaseModel):
    """Structured output schema for L13."""

    intent: Literal["qa", "explain", "summarize", "revise", "quiz"] = Field(
        description="The classified intent of the student's request."
    )


@timed("intent")
async def intent_node(state: TaskState) -> dict:
    if settings.llm.backend == "fake":
        return {"intent": "qa"}

    llm = get_llm(temperature=settings.llm.classifier_temperature)
    structured = llm.with_structured_output(IntentDecision)
    system, user = render_pair("intent.j2", question=state["standalone_question"])
    decision: IntentDecision = await structured.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return {"intent": decision.intent}
