"""Self-check node — strict refusal gate per L6.

One LLM call over all 5 reranked chunks. Strict bar: "Based ONLY on these
chunks, can the student's question be fully answered? yes/no". Loose lets
ALLaM fill gaps by inventing — that's exactly the failure mode L6 fences off.

Only gates `qa` and `explain` intents per L6. `summarize / revise / quiz`
skip the gate and go straight to generate — if retrieval returned chunks at
all, there's nothing to "answer" so the check is meaningless.

Backend selector:
  - backend=fake → always passes (Phase-A canned, so the no-API-key smoke
    run still works).
  - backend=openrouter → real LLM call with structured output.

Verdict + rerank scores are written to `state.debug` for L18 logging.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config import settings
from src.graph.client import get_llm
from src.graph.prompts import render_pair
from src.graph.state import TaskState

GATED_INTENTS = {"qa", "explain"}


class SelfCheckDecision(BaseModel):
    """Structured output for the L6 self-check."""

    passed: bool = Field(
        description="True if the chunks contain enough to fully answer the question."
    )
    reason: str = Field(
        description="One short sentence justifying the decision."
    )


async def self_check_node(state: TaskState) -> dict:
    debug = dict(state.get("debug") or {})
    intent = state.get("intent", "qa")

    if intent not in GATED_INTENTS:
        debug["self_check_verdict"] = "skipped"
        return {"self_check_passed": True, "debug": debug}

    if settings.llm.backend == "fake":
        debug["self_check_verdict"] = "yes (stub)"
        return {"self_check_passed": True, "debug": debug}

    llm = get_llm(temperature=settings.llm.classifier_temperature)
    structured = llm.with_structured_output(SelfCheckDecision)
    system, user = render_pair(
        "self_check.j2",
        question=state["standalone_question"],
        chunks=state.get("chunks") or [],
    )
    decision: SelfCheckDecision = await structured.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )
    debug["self_check_verdict"] = "yes" if decision.passed else "no"
    debug["self_check_reason"] = decision.reason
    return {"self_check_passed": decision.passed, "debug": debug}
