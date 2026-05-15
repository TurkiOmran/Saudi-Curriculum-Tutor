"""Generate node — grounded answer with inline `[n]` citations.

Implements §4.4 / L5: ALLaM (or OpenRouter dev LLM) writes the answer
using ONLY the retrieved chunks, with inline `[n]` markers. The
downstream `citations` node only parses these markers — it never invents
a chunk↔number mapping.

The prompt template (`prompts/generate.j2`) branches on `state.intent` to
emit per-mode instructions (qa / explain / summarize / revise / quiz —
L12). Language is conditioned via `state.language` (set by the L7 rewrite
node, or by the L16 regex fallback).

Token streaming: this node calls `llm.astream(...)` and concatenates the
deltas. When the outer graph is invoked via `astream_events`, those
deltas bubble up as `on_chat_model_stream` events — that's the seam the
Chainlit UI hooks into (L11, L21).

Backend selector:
  - backend=fake → canned Phase-A stub so no-API-key smoke runs work.
  - backend=openrouter → streamed real LLM call.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.graph.client import get_llm
from src.graph.prompts import render_pair
from src.graph.state import TaskState


async def generate_node(state: TaskState) -> dict:
    if settings.llm.backend == "fake":
        question = state.get("standalone_question", "")
        answer = (
            f"[stub] Based on the retrieved chunks, here's a placeholder answer "
            f"about: {question}. The real grounding contract is now live but "
            f"backend=fake skips the LLM call. [1]"
        )
        return {"answer": answer, "refused": False}

    llm = get_llm(temperature=settings.llm.generation_temperature)
    system, user = render_pair(
        "generate.j2",
        question=state["standalone_question"],
        chunks=state.get("chunks") or [],
        intent=state.get("intent", "qa"),
        language=state.get("language", "en"),
    )

    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    # Stream so per-token events propagate to outer.astream_events (L11, L21).
    parts: list[str] = []
    async for chunk in llm.astream(messages):
        content = getattr(chunk, "content", None)
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            # Some providers return content as a list of dicts; pull text parts.
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])

    answer = "".join(parts)
    return {"answer": answer, "refused": False}
