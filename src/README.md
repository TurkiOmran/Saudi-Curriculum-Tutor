# `src/` — Aleem source code

All Python for the Aleem RAG tutor lives here. Organised by pipeline stage
so each module has a single, narrow responsibility.

## Module map

| Folder         | Purpose                                                              | Status |
| -------------- | -------------------------------------------------------------------- | ------ |
| `retrieval/`   | Chroma client, Jina-v4 embedding function, collection setup script   | ✅ scaffolded |
| `ui/`          | Chainlit app — grade picker, subject picker, message handlers        | ✅ scaffolded (stub handler) |
| `ingest/`      | OCR + chunking pipeline → adds documents to Chroma                   | ⬜ not built |
| `graph/`       | LangGraph orchestration — rewrite, decompose, intent, retrieve, self-check, generate, refuse, citations (`RESPONSE_WORKFLOW.md` L9, L10) | ⬜ not built |

> The old `agent/` + `generation/` split is superseded. All query-path code lives in `graph/` per `RESPONSE_WORKFLOW.md` L10.

Pipeline flow (left-to-right is offline → online):

```
src/ingest/  →  Chroma collections  →  src/retrieval/  →  src/graph/  →  src/ui/
   (once)         (persisted)            (per query)       (per query)     (live)
```

## Running pieces today

```bash
# From the repo root.

# 1. Install dependencies (uv reads pyproject.toml + uv.lock; manages Python
#    3.11 automatically). For the pip fallback, see SETUP.md §3.
uv sync

# 2. Create the empty Chroma collections.
uv run python -m src.retrieval.init_chroma

# 3. Launch the Chainlit UI shell (no real retrieval wired in yet).
#    Chainlit reads its config/markdown/public assets from the CWD, so
#    we run it from inside src/ui/. PYTHONPATH lets future imports of
#    `src.retrieval...` resolve once the pipeline is wired in.
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py)
```

## Reference

- `BUILD_SPEC.md` (repo root) — locked design decisions per pipeline stage.
- `README.md` (repo root) — project overview, problem statement, stack.

## Folder READMEs

Every subfolder has its own `README.md` with module-specific detail. Open
that first if you're working inside a folder.
