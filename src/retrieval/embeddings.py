"""Jina-v4 embedding function for ChromaDB.

Wraps `jinaai/jina-embeddings-v4` (HuggingFace) in Chroma's `EmbeddingFunction`
protocol so collections can call it transparently from `collection.add(...)`
and `collection.query(...)`.

The model is loaded lazily on the first `__call__` — instantiating this class
costs nothing. This matters because `init_chroma.py` constructs an instance
just to attach it to empty collections, and we don't want to pay the ~3GB
download / GPU warm-up there.

Task modes (Jina-v4 supports several; we use only `retrieval.passage` for
indexing and `retrieval.query` for query-time embedding):
    - "passage" → for documents being added to the index.
    - "query"   → for user queries at retrieval time.
"""

from __future__ import annotations

import os
from typing import Literal

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

JINA_MODEL_ID = "jinaai/jina-embeddings-v4"
TaskMode = Literal["passage", "query"]


class JinaV4EmbeddingFunction(EmbeddingFunction[Documents]):
    """Chroma-compatible embedder backed by jina-embeddings-v4.

    The HF model itself is loaded on first use. After that it's cached on
    the instance — re-use the same instance across calls to avoid reloading.
    """

    def __init__(self, task_mode: TaskMode = "passage") -> None:
        self.task_mode: TaskMode = task_mode
        self._model = None  # lazy
        self._device: str | None = None

    @staticmethod
    def name() -> str:
        # Stable identifier Chroma stores in collection metadata so it can
        # warn if a future caller tries to attach a different embedder to
        # the same collection.
        return "jina-v4"

    def _load(self) -> None:
        if self._model is not None:
            return

        import torch
        from transformers import AutoModel

        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

        token = os.environ.get("HF_TOKEN") or None
        model = AutoModel.from_pretrained(
            JINA_MODEL_ID,
            trust_remote_code=True,
            token=token,
        )
        model.to(device)
        model.eval()

        self._model = model
        self._device = device

    def __call__(self, input: Documents) -> Embeddings:
        self._load()
        texts = list(input)
        if not texts:
            return []

        # Jina-v4 exposes encode_text(texts, task=..., prompt_name=...).
        # `task="retrieval"` + prompt_name "passage"/"query" selects the
        # appropriate adapter for asymmetric retrieval.
        embeddings = self._model.encode_text(  # type: ignore[union-attr]
            texts=texts,
            task="retrieval",
            prompt_name=self.task_mode,
        )

        # encode_text may return a torch.Tensor or list[Tensor]; normalise.
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [e.tolist() for e in embeddings]
