"""Inner graph integration (L9). Runs end-to-end with fake LLM backend."""

from __future__ import annotations

from src.graph.inner import inner_graph


async def test_qa_happy_path(make_task_state):
    state = make_task_state(standalone_question="What is photosynthesis?")
    result = await inner_graph.ainvoke(state)

    assert result["intent"] == "qa"
    assert result["self_check_passed"] is True
    assert result["refused"] is False
    assert result["answer"]
    # Fake generate writes `[1]` so citations must resolve one
    assert len(result["citations"]) == 1
    # Retrieve stub returns 3 chunks
    assert len(result["chunks"]) == 3


async def test_refusal_path_when_self_check_fails(make_task_state, monkeypatch):
    """Force the gate to fail and confirm refuse path renders L1 phrase."""
    async def _fake_self_check(state):
        debug = dict(state.get("debug") or {})
        debug["self_check_verdict"] = "no"
        return {"self_check_passed": False, "debug": debug}

    monkeypatch.setattr("src.graph.inner.self_check_node", _fake_self_check)

    # Need to rebuild the inner graph with the patched node
    from langgraph.graph import StateGraph

    from src.graph.nodes.chat import chat_node
    from src.graph.nodes.citations import citations_node
    from src.graph.nodes.generate import generate_node
    from src.graph.nodes.intent import intent_node
    from src.graph.nodes.refuse import refuse_node
    from src.graph.nodes.retrieve import retrieve_node
    from src.graph.state import TaskState

    g = StateGraph(TaskState)
    g.add_node("intent", intent_node)
    g.add_node("chat", chat_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("self_check", _fake_self_check)
    g.add_node("generate", generate_node)
    g.add_node("refuse", refuse_node)
    g.add_node("citations", citations_node)
    g.set_entry_point("intent")
    g.add_conditional_edges(
        "intent",
        lambda s: "chat" if s.get("intent") == "chat" else "retrieve",
        {"chat": "chat", "retrieve": "retrieve"},
    )
    g.add_edge("retrieve", "self_check")
    g.add_conditional_edges(
        "self_check",
        lambda s: "generate" if s.get("self_check_passed") else "refuse",
        {"generate": "generate", "refuse": "refuse"},
    )
    g.add_edge("generate", "citations")
    g.add_edge("refuse", "citations")
    g.add_edge("citations", "__end__")
    g.add_edge("chat", "__end__")
    forced = g.compile()

    state = make_task_state(standalone_question="off-topic question", language="en")
    result = await forced.ainvoke(state)

    assert result["refused"] is True
    assert "couldn't find this" in result["answer"]
    # Citations short-circuit on refuse
    assert result["citations"] == []


async def test_chat_path_bypasses_retrieve(make_task_state, monkeypatch):
    """When intent=chat, retrieve / self_check must NOT run."""
    state = make_task_state()

    # Force the intent classifier to return "chat"
    async def _force_chat(_state):
        return {"intent": "chat"}

    monkeypatch.setattr("src.graph.inner.intent_node", _force_chat)

    # Re-import / rebuild the graph with the patched intent
    from langgraph.graph import StateGraph

    from src.graph.nodes.chat import chat_node
    from src.graph.nodes.citations import citations_node
    from src.graph.nodes.generate import generate_node
    from src.graph.nodes.refuse import refuse_node
    from src.graph.nodes.retrieve import retrieve_node
    from src.graph.nodes.self_check import self_check_node
    from src.graph.state import TaskState

    retrieve_calls = {"n": 0}

    async def _spy_retrieve(s):
        retrieve_calls["n"] += 1
        return await retrieve_node(s)

    g = StateGraph(TaskState)
    g.add_node("intent", _force_chat)
    g.add_node("chat", chat_node)
    g.add_node("retrieve", _spy_retrieve)
    g.add_node("self_check", self_check_node)
    g.add_node("generate", generate_node)
    g.add_node("refuse", refuse_node)
    g.add_node("citations", citations_node)
    g.set_entry_point("intent")
    g.add_conditional_edges(
        "intent",
        lambda s: "chat" if s.get("intent") == "chat" else "retrieve",
        {"chat": "chat", "retrieve": "retrieve"},
    )
    g.add_edge("retrieve", "self_check")
    g.add_conditional_edges(
        "self_check",
        lambda s: "generate" if s.get("self_check_passed") else "refuse",
        {"generate": "generate", "refuse": "refuse"},
    )
    g.add_edge("generate", "citations")
    g.add_edge("refuse", "citations")
    g.add_edge("citations", "__end__")
    g.add_edge("chat", "__end__")
    forced = g.compile()

    result = await forced.ainvoke(state)

    assert result["intent"] == "chat"
    assert retrieve_calls["n"] == 0
    assert result.get("refused") in (False, None)
    assert result["answer"]
