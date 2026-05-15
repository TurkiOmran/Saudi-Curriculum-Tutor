"""Rewrite-history node — Phase A passthrough.

Per L7, this rewrites the user's message into a self-contained question
using the last N turns of chat history. Per L16, the same call also returns
the detected language (ar/en) via structured output.

Phase A: pure passthrough so the rest of the pipeline can run. Language is
detected by a regex fallback (Arabic Unicode block) per L16. Phase E lands
the real LLM call.

Bypassed entirely when `features.history_rewrite_enabled: false` — the
regex fallback for language remains the only logic, which is exactly what
the cut-it case looks like.
"""

from __future__ import annotations

import re

from src.graph.state import Language, OuterState

_ARABIC_RANGE = re.compile(r"[؀-ۿ]")


def detect_language_fallback(text: str) -> Language:
    """Regex fallback per L16 — used when L7 LLM rewrite is disabled."""
    return "ar" if _ARABIC_RANGE.search(text) else "en"


async def rewrite_node(state: OuterState) -> dict:
    # Phase A: no LLM, pass the query through unchanged.
    # Phase E will replace this body with a structured-output LLM call.
    user_query = state["user_query"]
    return {
        "standalone_question": user_query,
        "language": detect_language_fallback(user_query),
    }
