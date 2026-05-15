"""Self-check node — Phase A stub.

Returns `passed=True` so the graph routes to `generate`. Phase C replaces
this with a strict ALLaM/OpenRouter call over all 5 reranked chunks per L6.

Per L6, self-check only gates `qa` and `explain` intents — `summarize`,
`revise`, `quiz` skip the gate and go straight to generate. The skip is
implemented here so Phase C only has to swap the LLM call, not the routing.
"""

from __future__ import annotations

from src.graph.state import TaskState

GATED_INTENTS = {"qa", "explain"}


async def self_check_node(state: TaskState) -> dict:
    intent = state.get("intent", "qa")
    if intent not in GATED_INTENTS:
        debug = dict(state.get("debug") or {})
        debug["self_check_verdict"] = "skipped"
        return {"self_check_passed": True, "debug": debug}

    # Phase A: stub always passes.
    debug = dict(state.get("debug") or {})
    debug["self_check_verdict"] = "yes (stub)"
    return {"self_check_passed": True, "debug": debug}
