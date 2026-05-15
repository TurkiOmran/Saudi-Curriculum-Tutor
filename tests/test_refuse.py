"""Refusal node (L1). Canonical phrase + related lesson titles."""

from __future__ import annotations

import pytest

from src.graph.nodes.refuse import REFUSAL_AR, REFUSAL_EN, refuse_node
from src.graph.state import Chunk


def _chunk(lesson: str) -> Chunk:
    return Chunk(
        text="t",
        grade=7,
        subject="islamic_studies",
        book="b",
        chapter="ch",
        lesson_title=lesson,
        page=1,
        content_type="lesson_body",
    )


@pytest.fixture
def chunks_with_dupes():
    # 5 chunks across 3 unique lesson titles — top-3 cap + dedup test
    return [
        _chunk("Lesson A"),
        _chunk("Lesson B"),
        _chunk("Lesson A"),   # dup of A → must dedup
        _chunk("Lesson C"),
        _chunk("Lesson D"),   # past top-3 boundary
    ]


async def test_refuse_english_canonical_phrase(chunks_with_dupes):
    out = await refuse_node({"language": "en", "chunks": chunks_with_dupes})
    assert out["refused"] is True
    assert out["answer"].startswith(REFUSAL_EN)


async def test_refuse_arabic_canonical_phrase(chunks_with_dupes):
    out = await refuse_node({"language": "ar", "chunks": chunks_with_dupes})
    assert out["refused"] is True
    assert out["answer"].startswith(REFUSAL_AR)


async def test_refuse_dedupes_lessons_within_top_3(chunks_with_dupes):
    out = await refuse_node({"language": "en", "chunks": chunks_with_dupes})
    # Top-3 chunks are [A, B, A]. Dedup → [A, B]. C is past the slice, never seen.
    assert "Lesson A" in out["answer"]
    assert "Lesson B" in out["answer"]
    assert "Lesson C" not in out["answer"]
    assert "Lesson D" not in out["answer"]


async def test_refuse_no_chunks_still_renders_phrase():
    out = await refuse_node({"language": "en", "chunks": []})
    assert out["answer"] == REFUSAL_EN
    assert out["refused"] is True
