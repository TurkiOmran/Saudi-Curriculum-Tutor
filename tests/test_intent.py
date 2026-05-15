"""Intent node (L13). Fake-backend default + chat-heuristic fallback."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.graph.nodes.intent import IntentDecision, _looks_like_chat, intent_node


@pytest.mark.parametrize(
    "msg",
    [
        "hi",
        "hello there",
        "hey",
        "thanks",
        "thank you",
        "what can you do?",
        "who are you",
        "السلام عليكم",
        "مرحبا",
        "شكراً",
    ],
)
def test_looks_like_chat_true(msg):
    assert _looks_like_chat(msg) is True


@pytest.mark.parametrize(
    "msg",
    [
        "What is photosynthesis?",
        "Explain the Calvin cycle in detail please",
        "Summarize chapter 3",
        "Quiz me on the two stages",
        "",
    ],
)
def test_looks_like_chat_false(msg):
    assert _looks_like_chat(msg) is False


async def test_intent_fake_returns_qa(make_task_state):
    state = make_task_state()
    out = await intent_node(state)
    assert out["intent"] == "qa"


def test_intent_decision_schema_accepts_six_intents():
    # All six should validate; anything else raises
    for v in ("qa", "explain", "summarize", "revise", "quiz", "chat"):
        assert IntentDecision(intent=v).intent == v
    with pytest.raises(ValidationError):
        IntentDecision(intent="teacher-support")
