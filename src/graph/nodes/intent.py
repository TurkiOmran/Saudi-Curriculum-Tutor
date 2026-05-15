"""Intent node — Phase A stub.

Returns `"qa"` so the inner graph routes through the standard self-check
gate. Phase C swaps in a real `llm.with_structured_output(IntentDecision)`
call per L13.
"""

from __future__ import annotations

from src.graph.state import TaskState


async def intent_node(state: TaskState) -> dict:
    return {"intent": "qa"}
