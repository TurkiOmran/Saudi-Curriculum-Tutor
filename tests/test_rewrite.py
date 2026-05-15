"""Rewrite node (L7) + language fallback (L16)."""

from __future__ import annotations

from src.graph.nodes.rewrite import detect_language_fallback, rewrite_node


def test_language_fallback_english():
    assert detect_language_fallback("What is photosynthesis?") == "en"
    assert detect_language_fallback("hello world") == "en"
    assert detect_language_fallback("") == "en"   # empty → default


def test_language_fallback_arabic():
    assert detect_language_fallback("ما هو التمثيل الضوئي؟") == "ar"
    assert detect_language_fallback("مرحبا") == "ar"
    # Mixed: any Arabic char → ar
    assert detect_language_fallback("hello مرحبا") == "ar"


async def test_rewrite_fake_backend_passthrough(make_outer_state):
    state = make_outer_state(user_query="quiz me on that")
    out = await rewrite_node(state)
    # Fake backend returns the user query unchanged + regex language
    assert out["standalone_question"] == "quiz me on that"
    assert out["language"] == "en"


async def test_rewrite_arabic_query_detected(make_outer_state):
    state = make_outer_state(user_query="ما هو هذا؟")
    out = await rewrite_node(state)
    assert out["language"] == "ar"
    assert out["standalone_question"] == "ما هو هذا؟"
