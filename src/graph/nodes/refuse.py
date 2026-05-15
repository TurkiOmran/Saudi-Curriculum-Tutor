"""Refuse node — canonical refusal per L1.

Pure Python, no LLM. Renders the canonical phrase + lesson titles of the
top-3 retrieved chunks. This logic is correct for both Phase A (stub) and
Phase C (real) — only the upstream `self_check` decision changes.
"""

from __future__ import annotations

from src.graph.logging import timed
from src.graph.state import TaskState

REFUSAL_AR = "لم أجد هذا في الكتاب المدرسي"
REFUSAL_EN = "I couldn't find this in your textbook"

RELATED_HEADER_AR = "مواضيع ذات صلة في كتابك:"
RELATED_HEADER_EN = "Related topics in your textbook:"


@timed("refuse")
async def refuse_node(state: TaskState) -> dict:
    language = state.get("language", "en")
    chunks = state.get("chunks") or []

    if language == "ar":
        phrase = REFUSAL_AR
        related_header = RELATED_HEADER_AR
    else:
        phrase = REFUSAL_EN
        related_header = RELATED_HEADER_EN

    # Top-3 parent lesson titles, deduped while preserving order.
    seen: set[str] = set()
    titles: list[str] = []
    for c in chunks[:3]:
        if c.lesson_title and c.lesson_title not in seen:
            seen.add(c.lesson_title)
            titles.append(c.lesson_title)

    bullet_list = "\n".join(f"- {t}" for t in titles)
    answer = f"{phrase}\n\n{related_header}\n{bullet_list}" if titles else phrase

    return {"answer": answer, "refused": True}
