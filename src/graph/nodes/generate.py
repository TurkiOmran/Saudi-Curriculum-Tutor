"""Generate node — Phase A stub.

Returns a canned answer with a `[1]` citation marker so the citations
node downstream has something to parse. Phase C replaces this with a
Jinja-rendered prompt + streamed ALLaM/OpenRouter call per L5 and L19.
"""

from __future__ import annotations

from src.graph.state import TaskState


async def generate_node(state: TaskState) -> dict:
    question = state.get("standalone_question", "")
    answer = (
        f"[stub] Based on the retrieved chunks, here's a placeholder answer "
        f"about: {question}. The real grounding contract lands in Phase C. [1]"
    )
    return {"answer": answer, "refused": False}
