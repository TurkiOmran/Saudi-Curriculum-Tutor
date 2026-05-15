"""Chat node — friendly bounded reply for non-curriculum messages (L22).

When `intent` classifier returns `"chat"` (greetings, small talk, meta-
questions, "what can you do" type asks), the inner graph routes here
instead of `retrieve`. The prompt is bounded — must NOT answer factual
questions, must stay in the student's language, must keep the reply short.

This preserves L1's strict-grounding contract for the five educational
intents (qa/explain/summarize/revise/quiz) while letting Aleem feel
chatbot-like on social input.

Streams tokens via `llm.astream()` so the Chainlit UI can render them
live (same hook as `generate`).
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.graph.client import get_llm
from src.graph.logging import timed
from src.graph.prompts import render_pair
from src.graph.state import TaskState

# Deterministic canned replies for backend=fake (no API key required).
_FAKE_REPLIES: dict[str, str] = {
    "en": "Hi! I'm Aleem — I help with your textbook. What topic would you like to explore?",
    "ar": "أهلاً! أنا عليم — أساعدك في كتابك المدرسي. ما الموضوع الذي تود استكشافه؟",
}


@timed("chat")
async def chat_node(state: TaskState) -> dict:
    language = state.get("language", "en")

    if settings.llm.backend == "fake":
        return {
            "answer": _FAKE_REPLIES.get(language, _FAKE_REPLIES["en"]),
            "refused": False,
        }

    llm = get_llm(temperature=settings.llm.generation_temperature)
    system, user = render_pair(
        "chat.j2",
        question=state["standalone_question"],
        grade=state["grade"],
        subject=state["subject"],
        language=language,
    )
    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    parts: list[str] = []
    try:
        async for chunk in llm.astream(messages):
            content = getattr(chunk, "content", None)
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
    except Exception:  # noqa: BLE001 — fall back to a friendly canned reply
        return {
            "answer": _FAKE_REPLIES.get(language, _FAKE_REPLIES["en"]),
            "refused": False,
        }

    return {"answer": "".join(parts), "refused": False}
