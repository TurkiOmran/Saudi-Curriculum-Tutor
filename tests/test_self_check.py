"""Self-check (L6). Strict gate only for qa / explain; others skip."""

from __future__ import annotations

import pytest

from src.graph.nodes.self_check import GATED_INTENTS, self_check_node


@pytest.mark.parametrize("intent", ["summarize", "revise", "quiz", "chat"])
async def test_non_gated_intents_skip(intent, make_task_state):
    state = make_task_state()
    state["intent"] = intent
    out = await self_check_node(state)
    assert out["self_check_passed"] is True
    assert out["debug"]["self_check_verdict"] == "skipped"


@pytest.mark.parametrize("intent", ["qa", "explain"])
async def test_gated_intents_fake_passes(intent, make_task_state):
    state = make_task_state()
    state["intent"] = intent
    out = await self_check_node(state)
    assert out["self_check_passed"] is True
    assert "(stub)" in out["debug"]["self_check_verdict"]


def test_gated_intents_set_is_qa_and_explain():
    # Locks L6 — qa + explain only, never widen without a new decision
    assert GATED_INTENTS == {"qa", "explain"}
