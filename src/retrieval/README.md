# `src/retrieval/` — embeddings + Chroma client

Owns everything between the Jina-v4 embedding model and the persisted
Chroma store. Other modules (`ingest/`, `agent/`, `ui/`) talk to Chroma
*only* through helpers in this folder.

## Files

| File                | What it does                                                                 |
| ------------------- | ---------------------------------------------------------------------------- |
| `embeddings.py`     | `JinaV4EmbeddingFunction` — Chroma-compatible wrapper around `jinaai/jina-embeddings-v4`. Lazy-loads the HF model on first call. |
| `chroma_client.py`  | `get_client()`, `get_collection(grade, task_mode)`, plus the `GRADES` and `SUBJECTS` constants and the metadata schema docstring. |
| `init_chroma.py`    | One-time setup script. Creates `grade_4`, `grade_7`, `grade_8`, `grade_10` collections with Jina-v4 attached. Idempotent. |
| `reranker.py`       | `JinaReranker` — cross-encoder rerank using `jinaai/jina-reranker-v2-base-multilingual`. Singleton, lazy-loaded. |

## How to use

### One-time setup (creates the empty collections)

```bash
uv run python -m src.retrieval.init_chroma
```

Logs which collections were created vs already existed. Safe to re-run.

### Open a collection for querying

```python
from src.retrieval.chroma_client import get_collection

# Query-time embedding mode (asymmetric retrieval — query side).
col = get_collection(grade=7, task_mode="query")

result = col.query(
    query_texts=["ما هي قواعد المد؟"],
    n_results=20,
    where={"subject": "arabic"},   # subject is a metadata filter, BUILD_SPEC §4.3
)
```

### Open a collection for ingestion

```python
from src.retrieval.chroma_client import get_collection

col = get_collection(grade=7, task_mode="passage")
col.add(
    documents=["chunk text 1", "chunk text 2"],
    metadatas=[{...}, {...}],   # see BUILD_SPEC §4.2 for required keys
    ids=["chunk_1", "chunk_2"],
)
```

## Key design points

- **One collection per grade**, not per (grade, subject). Subject is a
  metadata filter applied at query time. Rationale: grade isolation is
  structural and load-bearing; subject is fluid. See `BUILD_SPEC.md §4.3`.
- **Asymmetric retrieval**: passages embedded with `prompt_name="passage"`,
  queries with `prompt_name="query"`. The `task_mode` argument selects.
- **Lazy model load**: `JinaV4EmbeddingFunction.__init__` does not download
  or load Jina-v4 — that happens on first `__call__`. So `init_chroma.py`
  runs cheaply without GPU time.
- **Embedder must be re-attached on every `get_collection`** — Chroma
  persists data but not the embedding function instance. `chroma_client.get_collection`
  handles this for you.

## Env vars

| Var          | Effect                                              | Default       |
| ------------ | --------------------------------------------------- | ------------- |
| `HF_TOKEN`   | Used to download the (gated) Jina-v4 model weights. | not set       |
| `CHROMA_DIR` | Override where Chroma persists.                     | `./chroma`    |

## Not here

- OCR / parsing / chunking — `src/ingest/`.
- Generation, prompts, self-check — `src/graph/nodes/` (per `RESPONSE_WORKFLOW.md` L10).
