"""Chat node (L22). Fake-backend bilingual canned replies."""

from __future__ import annotations

from src.graph.nodes.chat import _FAKE_REPLIES, chat_node


async def test_chat_fake_english(make_task_state):
    state = make_task_state(language="en")
    out = await chat_node(state)
    assert out["answer"] == _FAKE_REPLIES["en"]
    assert out["refused"] is False


async def test_chat_fake_arabic(make_task_state):
    state = make_task_state(language="ar")
    out = await chat_node(state)
    assert out["answer"] == _FAKE_REPLIES["ar"]
    assert out["refused"] is False


async def test_chat_fake_no_citations_path(make_task_state):
    """Chat answers must NOT contain [n] citation markers."""
    state = make_task_state(language="en")
    out = await chat_node(state)
    assert "[1]" not in out["answer"]
    assert "[2]" not in out["answer"]
