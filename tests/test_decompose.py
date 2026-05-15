"""Decompose (L4). Fake-backend default + feature-flag bypass."""

from __future__ import annotations

from dataclasses import replace

from src.graph.nodes.decompose import decompose_node


async def test_fake_returns_single_task(make_outer_state):
    state = make_outer_state(user_query="explain X and quiz me")
    state["standalone_question"] = "explain X and quiz me"
    state["language"] = "en"
    out = await decompose_node(state)
    assert len(out["tasks"]) == 1
    task = out["tasks"][0]
    assert task["standalone_question"] == "explain X and quiz me"
    assert task["grade"] == state["grade"]
    assert task["subject"] == state["subject"]
    assert task["language"] == "en"


async def test_feature_flag_off_skips_llm_call(make_outer_state, monkeypatch):
    """When decomposition_enabled is False, decompose must NOT call get_llm."""
    from src.graph.nodes import decompose as decompose_mod

    new_features = replace(decompose_mod.settings.features, decomposition_enabled=False)
    new_settings = replace(decompose_mod.settings, features=new_features)
    monkeypatch.setattr("src.graph.nodes.decompose.settings", new_settings)

    called = {"hit": False}

    def _fail_if_called(*a, **kw):
        called["hit"] = True
        raise AssertionError("get_llm called when decomposition_enabled is False")

    monkeypatch.setattr("src.graph.nodes.decompose.get_llm", _fail_if_called)

    state = make_outer_state(user_query="compound query")
    state["standalone_question"] = "compound query"
    out = await decompose_node(state)
    assert len(out["tasks"]) == 1
    assert called["hit"] is False


async def test_history_propagates_to_tasks(make_outer_state):
    state = make_outer_state(
        user_query="follow up",
        history=[{"role": "user", "content": "hello"}],
    )
    state["standalone_question"] = "follow up"
    out = await decompose_node(state)
    assert out["tasks"][0]["history"] == [{"role": "user", "content": "hello"}]
