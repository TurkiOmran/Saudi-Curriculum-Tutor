"""Jinja prompt loader (L19). `render_pair` splits on the `---` divider."""

from __future__ import annotations

from src.graph.prompts import render


def test_render_intent_template_includes_six_intents():
    text = render("intent.j2", question="hello")
    # Spot-check that the prompt still lists all six intents per L22.
    for intent in ("qa", "explain", "summarize", "revise", "quiz", "chat"):
        assert f"- {intent}:" in text


def test_render_generate_template_branches_by_intent():
    chunks = []
    for_qa = render(
        "generate.j2", question="q", chunks=chunks, intent="qa", language="en"
    )
    for_quiz = render(
        "generate.j2", question="q", chunks=chunks, intent="quiz", language="en"
    )
    assert "Answer the student's question directly" in for_qa
    assert "3 short quiz questions" in for_quiz


def test_render_generate_template_language_branch():
    chunks = []
    en = render("generate.j2", question="q", chunks=chunks, intent="qa", language="en")
    ar = render("generate.j2", question="q", chunks=chunks, intent="qa", language="ar")
    assert "English" in en
    assert "Arabic" in ar
