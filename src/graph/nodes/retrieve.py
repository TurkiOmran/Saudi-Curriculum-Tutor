"""Retrieve node — Phase A stub.

Returns 3 hardcoded `Chunk` objects so the rest of the pipeline can run
end-to-end while Chroma is empty (per L2). The real implementation
(`query embed → Chroma top-20 → Jina rerank → top-5`) lands as a later
task — it's a single-file swap because the contract here matches the
metadata schema in `src/retrieval/chroma_client.py:8-18`.
"""

from __future__ import annotations

from src.graph.logging import timed
from src.graph.state import Chunk, TaskState

# Hardcoded chunks tagged with valid (grade, subject) so anything reading
# the metadata sees a realistic shape.
_STUB_CHUNKS: list[Chunk] = [
    Chunk(
        text=(
            "Photosynthesis is the process by which green plants use sunlight, "
            "water, and carbon dioxide to produce glucose and oxygen."
        ),
        grade=7,
        subject="islamic_studies",  # placeholder — replaced once retrieve() is real
        book="stub_book.pdf",
        chapter="Chapter 1",
        lesson_title="Stub Lesson — Photosynthesis Basics",
        page=12,
        content_type="lesson_body",
        rerank_score=0.94,
    ),
    Chunk(
        text=(
            "Chlorophyll, the green pigment in plant cells, absorbs light energy "
            "from the sun and converts it into chemical energy."
        ),
        grade=7,
        subject="islamic_studies",
        book="stub_book.pdf",
        chapter="Chapter 1",
        lesson_title="Stub Lesson — Photosynthesis Basics",
        page=13,
        content_type="lesson_body",
        rerank_score=0.81,
    ),
    Chunk(
        text=(
            "The two stages of photosynthesis are the light-dependent reactions "
            "and the Calvin cycle (light-independent reactions)."
        ),
        grade=7,
        subject="islamic_studies",
        book="stub_book.pdf",
        chapter="Chapter 1",
        lesson_title="Stub Lesson — Two Stages",
        page=15,
        content_type="definition",
        rerank_score=0.73,
    ),
]


@timed("retrieve")
async def retrieve_node(state: TaskState) -> dict:
    chunks = list(_STUB_CHUNKS)
    debug = dict(state.get("debug") or {})
    debug["rerank_scores"] = [c.rerank_score for c in chunks]
    return {"chunks": chunks, "debug": debug}
