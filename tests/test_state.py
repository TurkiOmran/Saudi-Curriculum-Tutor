"""State contracts — `Chunk`, `TaskState`, `OuterState` initializers."""

from __future__ import annotations

from src.graph.state import (
    Chunk,
    initial_outer_state,
    initial_task_state,
)


def test_chunk_dataclass_round_trip():
    c = Chunk(
        text="hello",
        grade=7,
        subject="islamic_studies",
        book="b.pdf",
        chapter="ch1",
        lesson_title="L1",
        page=3,
        content_type="lesson_body",
        rerank_score=0.5,
    )
    md = c.as_metadata()
    assert md["grade"] == 7
    assert md["lesson_title"] == "L1"
    assert md["page"] == 3
    assert md["rerank_score"] == 0.5


def test_initial_task_state_defaults():
    s = initial_task_state(grade=4, subject="arabic", standalone_question="q", language="ar")
    # Required fields land
    assert s["grade"] == 4
    assert s["subject"] == "arabic"
    assert s["standalone_question"] == "q"
    assert s["language"] == "ar"
    # Optional-but-initialized defaults
    assert s["chunks"] == []
    assert s["citations"] == []
    assert s["refused"] is False
    assert s["debug"] == {}
    assert s["history"] == []


def test_initial_task_state_with_history():
    history = [{"role": "user", "content": "hi"}]
    s = initial_task_state(
        grade=10, subject="math", standalone_question="q", language="en", history=history
    )
    assert s["history"] == history


def test_initial_outer_state_defaults():
    s = initial_outer_state(grade=7, subject="english", user_query="hello")
    assert s["grade"] == 7
    assert s["subject"] == "english"
    assert s["user_query"] == "hello"
    assert s["history"] == []
    assert s["tasks"] == []
    assert s["debug"] == {}
