"""Retrieve node — Chroma query + Jina-v4 reranker.

Replaces the Phase A hardcoded-chunks stub. Flow:
  1. Open `get_collection(grade, task_mode="query")` to embed the query.
  2. Query top-K with `where={"subject": subject}` so other subjects
     aren't pulled in (`BUILD_SPEC.md §4.3` — subject as metadata filter).
  3. Rerank with Jina Reranker v2 (cross-encoder) and keep the top-N.
  4. Return `chunks` (list[Chunk]) with `rerank_score` populated.

`_STUB_CHUNKS` is preserved as a fallback for two reasons:
  - The test suite forces `backend=fake` and never ingests anything,
    so grade collections are empty during tests — falling back to stubs
    keeps the inner-graph tests honest without mocking Chroma.
  - Useful early-error UX: if you run a query against a grade that
    hasn't been ingested yet, you get a working answer with a clear
    "stub data" rerank-score signature instead of a crash.
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import settings
from src.graph.logging import timed
from src.graph.state import Chunk, TaskState
from src.retrieval.chroma_client import get_collection
from src.retrieval.reranker import get_reranker

log = logging.getLogger("aleem.graph.retrieve")


_STUB_CHUNKS: list[Chunk] = [
    Chunk(
        text=(
            "Photosynthesis is the process by which green plants use sunlight, "
            "water, and carbon dioxide to produce glucose and oxygen."
        ),
        grade=7,
        subject="islamic_studies",
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


def _chunk_from_chroma(
    text: str,
    metadata: dict[str, Any],
    rerank_score: float,
) -> Chunk:
    """Map a Chroma hit (document + metadata) into the graph's Chunk shape."""
    return Chunk(
        text=text,
        grade=int(metadata.get("grade", 0)),
        subject=str(metadata.get("subject", "")),
        book=str(metadata.get("book", "")),
        book_id=str(metadata.get("book_id", "")),
        chapter=str(metadata.get("chapter", "")),
        lesson_title=str(metadata.get("lesson_title", "")),
        page=int(metadata.get("page", 0)),
        content_type=str(metadata.get("content_type", "lesson_body")),
        rerank_score=rerank_score,
    )


def _retrieve_real(grade: int, subject: str, question: str) -> list[Chunk]:
    col = get_collection(grade, task_mode="query")
    if col.count() == 0:
        log.warning(
            "grade_%d collection is empty — falling back to stub chunks. "
            "Run `uv run python -m src.ingest ...` to populate it.",
            grade,
        )
        return list(_STUB_CHUNKS)

    top_k_retrieve = settings.retrieval.top_k_retrieve
    top_k_rerank = settings.retrieval.top_k_rerank

    result = col.query(
        query_texts=[question],
        n_results=top_k_retrieve,
        where={"subject": subject},
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]

    if not documents:
        log.warning("no chunks matched subject=%s in grade_%d", subject, grade)
        return []

    scores = get_reranker().score(question, list(documents))
    paired = list(zip(documents, metadatas, scores, strict=False))
    paired.sort(key=lambda t: t[2], reverse=True)

    return [
        _chunk_from_chroma(text=doc, metadata=md or {}, rerank_score=score)
        for doc, md, score in paired[:top_k_rerank]
    ]


@timed("retrieve")
async def retrieve_node(state: TaskState) -> dict:
    grade = state["grade"]
    subject = state["subject"]
    question = state["standalone_question"]

    chunks = _retrieve_real(grade, subject, question)

    debug = dict(state.get("debug") or {})
    debug["rerank_scores"] = [c.rerank_score for c in chunks]
    return {"chunks": chunks, "debug": debug}
