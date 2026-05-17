"""Graph state types.

`TaskState` and `OuterState` are the canonical state schemas for the inner
and outer LangGraph graphs respectively. See `RESPONSE_WORKFLOW.md` L9.

`Chunk` mirrors the metadata contract in
`src/retrieval/chroma_client.py:8-18` — the boundary where ingestion meets
the query path. Keep these in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

Intent = Literal["qa", "explain", "summarize", "revise", "quiz", "chat"]
Language = Literal["ar", "en"]


@dataclass(frozen=True)
class Chunk:
    """A retrieved + reranked textbook chunk.

    Matches the Chroma metadata schema documented at
    `src/retrieval/chroma_client.py:8-26` (OCR_implementation.md D8
    supersedes BUILD_SPEC §4.2). `text` is the document content;
    everything else is metadata.
    """

    text: str
    grade: int
    subject: str
    book: str
    chapter: str
    lesson_title: str
    page: int
    content_type: str  # lesson_body | example | exercise | definition
    book_id: str = ""  # stable short handle; D10 delete-by-book_id key
    rerank_score: float = 0.0

    def as_metadata(self) -> dict[str, Any]:
        return {
            "grade": self.grade,
            "subject": self.subject,
            "book": self.book,
            "book_id": self.book_id,
            "chapter": self.chapter,
            "lesson_title": self.lesson_title,
            "page": self.page,
            "content_type": self.content_type,
            "rerank_score": self.rerank_score,
        }


@dataclass(frozen=True)
class Citation:
    """A single rendered citation: marker index → chunk."""

    n: int
    chunk: Chunk


class TaskState(TypedDict, total=False):
    """Inner-graph state. One per atomic task (decompose can produce >1).

    Fields per L9:
      - inputs:  grade, subject, standalone_question, language, history
      - filled by nodes: intent, chunks, self_check_passed, answer,
                          citations, refused, debug

    Note on `history`: L7 promises that downstream nodes always receive a
    standalone question — that contract still holds. `history` is here
    only so the L22 `chat` node can reference recent turns naturally
    ("you just said hello"); educational nodes (qa/explain/summarize/
    revise/quiz) still ignore it and rely on `standalone_question`.
    """

    # Inputs
    grade: int
    subject: str
    standalone_question: str
    language: Language
    history: list[HistoryTurn]

    # Filled by nodes
    intent: Intent
    chunks: list[Chunk]
    self_check_passed: bool
    answer: str
    citations: list[Citation]
    refused: bool

    # Observability (L18 — dumped to JSONL at end)
    debug: dict[str, Any]


class HistoryTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class OuterState(TypedDict, total=False):
    """Outer-graph state. Holds session inputs + the list of TaskStates."""

    # Inputs (from Chainlit session)
    grade: int
    subject: str
    user_query: str
    history: list[HistoryTurn]

    # Filled by rewrite (L7 / L16)
    standalone_question: str
    language: Language

    # Filled by decompose (L4), updated by the inner-graph map
    tasks: list[TaskState]

    # Filled by merge
    final_answer: str

    # Observability
    debug: dict[str, Any]


def initial_task_state(
    grade: int,
    subject: str,
    standalone_question: str,
    language: Language,
    history: list[HistoryTurn] | None = None,
) -> TaskState:
    return TaskState(
        grade=grade,
        subject=subject,
        standalone_question=standalone_question,
        language=language,
        history=history or [],
        chunks=[],
        citations=[],
        refused=False,
        debug={},
    )


def initial_outer_state(
    grade: int,
    subject: str,
    user_query: str,
    history: list[HistoryTurn] | None = None,
) -> OuterState:
    return OuterState(
        grade=grade,
        subject=subject,
        user_query=user_query,
        history=history or [],
        tasks=[],
        debug={},
    )
