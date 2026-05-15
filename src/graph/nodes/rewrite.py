"""Rewrite-history node — turns a turn-relative message into a self-
contained question, plus detects language (L7 + L16).

Single LLM call returning a structured `{standalone_question, language}`
pair per L16 — no separate language node. Everything downstream
(decompose, intent, retrieve, ...) only ever sees the standalone form.

Backend / feature gates:
  - `features.history_rewrite_enabled: false` → no LLM call. The user
    query passes through unchanged and `language` is set via the regex
    fallback. This is the L7 cuttable path.
  - `llm.backend == "fake"`               → same passthrough behaviour
    as the disabled-feature path, so no-API-key runs still work.
  - Otherwise                              → real `llm.with_structured_output`
    call rendering `prompts/rewrite.j2` with the last
    `memory.max_turns * 2` history entries.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config import settings
from src.graph.client import get_llm
from src.graph.logging import timed
from src.graph.prompts import render_pair
from src.graph.state import Language, OuterState

_ARABIC_RANGE = re.compile(r"[؀-ۿ]")


class StandaloneQuery(BaseModel):
    """Structured output for the L7 rewrite + L16 language detection."""

    standalone_question: str = Field(
        description=(
            "The student's new message rewritten as a self-contained question. "
            "Resolve pronouns/ellipsis using the chat history. If already "
            "self-contained, return the message unchanged."
        )
    )
    language: Literal["ar", "en"] = Field(
        description="Language of the student's new message — 'ar' or 'en'."
    )


def detect_language_fallback(text: str) -> Language:
    """Regex fallback per L16 — used when L7 LLM rewrite is disabled."""
    return "ar" if _ARABIC_RANGE.search(text) else "en"


@timed("rewrite")
async def rewrite_node(state: OuterState) -> dict:
    user_query = state["user_query"]

    use_fallback = (
        not settings.features.history_rewrite_enabled
        or settings.llm.backend == "fake"
    )
    if use_fallback:
        return {
            "standalone_question": user_query,
            "language": detect_language_fallback(user_query),
        }

    history = (state.get("history") or [])[-(settings.memory.max_turns * 2):]
    llm = get_llm(temperature=settings.llm.classifier_temperature)
    structured = llm.with_structured_output(StandaloneQuery)
    system, user = render_pair("rewrite.j2", history=history, question=user_query)
    result: StandaloneQuery = await structured.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    return {
        "standalone_question": result.standalone_question or user_query,
        "language": result.language,
    }
