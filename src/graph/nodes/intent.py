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
    """Structured output schema for L13 (extended to 6 intents per L22)."""

    intent: Literal["qa", "explain", "summarize", "revise", "quiz", "chat"] = Field(
        description="The classified intent of the student's request."
    )


# Cheap heuristic used ONLY when the structured-output LLM call fails.
# Catches the obvious greetings / thanks / small-talk so the L22 chat
# path still fires when the classifier returns malformed output. The LLM
# is still the primary classifier — this just keeps the pipeline useful
# when the provider hiccups (e.g. Llama-3.3-70b/vLLM intermittent empty
# tool_call responses).
_CHAT_KEYWORDS_EN = {
    "hi", "hello", "hey", "yo", "sup", "howdy",
    "thanks", "thank", "thx", "ty",
    "bye", "goodbye", "cya",
    "ok", "okay", "cool", "nice", "good", "great",
    "who are you", "what can you do", "what are you",
}
_CHAT_KEYWORDS_AR = {
    "السلام", "مرحبا", "أهلا", "اهلا", "هاي",
    "شكرا", "شكراً", "ممنون",
    "مع السلامة", "وداعا",
    "من أنت", "ماذا تفعل", "ماذا يمكنك",
}


def _looks_like_chat(text: str) -> bool:
    """True if the message is obviously conversational (fallback heuristic)."""
    t = (text or "").strip().lower()
    if not t:
        return False
    # Long messages with a question mark are unlikely to be small talk.
    if "?" in t and len(t.split()) > 3:
        return False
    if any(kw in t for kw in _CHAT_KEYWORDS_EN):
        return True
    if any(kw in text for kw in _CHAT_KEYWORDS_AR):
        return True
    return False


@timed("intent")
async def intent_node(state: TaskState) -> dict:
    if settings.llm.backend == "fake":
        return {"intent": "qa"}

    structured = get_llm(
        temperature=settings.llm.classifier_temperature,
        structured=IntentDecision,
    )
    system, user = render_pair("intent.j2", question=state["standalone_question"])
    try:
        decision: IntentDecision = await structured.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return {"intent": decision.intent}
    except Exception as exc:  # noqa: BLE001 — provider/parser failures, recover gracefully
        debug = dict(state.get("debug") or {})
        debug["intent_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        fallback = "chat" if _looks_like_chat(state.get("standalone_question", "")) else "qa"
        debug["intent_fallback"] = fallback
        return {"intent": fallback, "debug": debug}
