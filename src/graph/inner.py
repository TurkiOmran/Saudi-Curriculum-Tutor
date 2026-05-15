"""Inner graph — `run_one(task)`.

Per-task pipeline (L9):
    intent → retrieve → self_check → (generate | refuse) → citations → END

Built as a LangGraph `StateGraph` over `TaskState`. The conditional edge
after `self_check` implements the L1 / L6 refusal-vs-generate routing.
The compiled graph is exposed as `inner_graph` — call `.ainvoke(task)` to
run one task end-to-end, or invoke from a parent graph (events propagate
to the parent's `astream_events`).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from src.graph.nodes.chat import chat_node
from src.graph.nodes.citations import citations_node
from src.graph.nodes.generate import generate_node
from src.graph.nodes.intent import intent_node
from src.graph.nodes.refuse import refuse_node
from src.graph.nodes.retrieve import retrieve_node
from src.graph.nodes.self_check import self_check_node
from src.graph.state import TaskState


def _route_after_intent(state: TaskState) -> str:
    """L22 — `chat` intent skips retrieve/self_check entirely."""
    return "chat" if state.get("intent") == "chat" else "retrieve"


def _route_after_self_check(state: TaskState) -> str:
    return "generate" if state.get("self_check_passed") else "refuse"


def _build_inner() -> Any:
    g = StateGraph(TaskState)
    g.add_node("intent", intent_node)
    g.add_node("chat", chat_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("self_check", self_check_node)
    g.add_node("generate", generate_node)
    g.add_node("refuse", refuse_node)
    g.add_node("citations", citations_node)

    g.set_entry_point("intent")
    g.add_conditional_edges(
        "intent",
        _route_after_intent,
        {"chat": "chat", "retrieve": "retrieve"},
    )
    g.add_edge("retrieve", "self_check")
    g.add_conditional_edges(
        "self_check",
        _route_after_self_check,
        {"generate": "generate", "refuse": "refuse"},
    )
    g.add_edge("generate", "citations")
    g.add_edge("refuse", "citations")
    g.add_edge("citations", END)
    g.add_edge("chat", END)   # chat bypasses citations — no [n] markers expected

    return g.compile()


inner_graph = _build_inner()
