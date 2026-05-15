"""Citation parsing (L5 / L14). Pure-Python regex node."""

from __future__ import annotations

import pytest

from src.graph.nodes.citations import citations_node
from src.graph.state import Chunk


def _chunk(idx: int) -> Chunk:
    return Chunk(
        text=f"chunk {idx} text",
        grade=7,
        subject="islamic_studies",
        book="b",
        chapter="ch",
        lesson_title=f"Lesson {idx}",
        page=idx,
        content_type="lesson_body",
    )


@pytest.fixture
def three_chunks():
    return [_chunk(1), _chunk(2), _chunk(3)]


async def test_parses_in_order_markers(three_chunks):
    state = {"answer": "A [1] B [2] C [3]", "chunks": three_chunks, "refused": False}
    out = await citations_node(state)
    assert [c.n for c in out["citations"]] == [1, 2, 3]
    assert out["citations"][0].chunk.lesson_title == "Lesson 1"


async def test_deduplicates_repeat_markers(three_chunks):
    state = {"answer": "[1] foo [1] bar [2]", "chunks": three_chunks, "refused": False}
    out = await citations_node(state)
    assert [c.n for c in out["citations"]] == [1, 2]


async def test_out_of_range_marker_logged_not_returned(three_chunks):
    state = {"answer": "claim [5]", "chunks": three_chunks, "refused": False}
    out = await citations_node(state)
    assert out["citations"] == []
    assert out["debug"]["citations_malformed"] == [5]


async def test_refused_short_circuits(three_chunks):
    state = {"answer": "I couldn't find this [1]", "chunks": three_chunks, "refused": True}
    out = await citations_node(state)
    assert out["citations"] == []


async def test_no_markers_returns_empty(three_chunks):
    state = {"answer": "no citations here", "chunks": three_chunks, "refused": False}
    out = await citations_node(state)
    assert out["citations"] == []
    assert out["debug"]["citations_count"] == 0
