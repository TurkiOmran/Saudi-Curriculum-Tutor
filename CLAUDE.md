# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Aleem is a curriculum-grounded RAG tutor over official Saudi Ministry of Education textbooks. Every answer must be traceable to a specific grade-level textbook chunk; refusal is a first-class outcome. This file is a **map** — it tells you where to look, not how each piece works.

---

## Where to look first

| If you need to…                          | Open                                          |
| ---------------------------------------- | --------------------------------------------- |
| Understand the project pitch / problem   | `README.md`                                   |
| Find a **locked design decision**        | `BUILD_SPEC.md` (numbered sections §1–§10)    |
| Find an **agentic-layer decision** (L1–L21) | `RESPONSE_WORKFLOW.md`                     |
| Get the repo running from a fresh clone  | `SETUP.md`                                    |
| Work inside a subfolder                  | That folder's `README.md` (every dir has one) |

When the user asks "why was X decided this way?", grep `BUILD_SPEC.md` first, then `RESPONSE_WORKFLOW.md`. Both files use **stable section/decision IDs** (`§4.5`, `L11`) — cite those IDs back to the user instead of paraphrasing.

`RESPONSE_WORKFLOW.md` overrides `BUILD_SPEC.md` where they disagree (it's the active grilling doc for the agentic layer — currently on the `agentic-pipeline` branch).

---

## Repo layout (navigational)

```
Aleem/
├── README.md                 # pitch + target architecture
├── BUILD_SPEC.md             # §1–§10: locked spec, the "build to this" doc
├── RESPONSE_WORKFLOW.md      # L1–L18: agentic-layer decisions (live)
├── SETUP.md                  # how to install + run
├── Capstone_Proposal_*.md    # original proposal (historical context)
│
├── pyproject.toml            # deps (exact-pinned)
├── uv.lock                   # source of truth for the environment
├── requirements.txt          # auto-generated pip fallback (do NOT hand-edit)
├── .python-version           # pinned to 3.11
├── .env.example              # template; copy to .env (gitignored)
│
├── src/
│   ├── retrieval/            # ✅ scaffolded — Chroma client + Jina-v4 embedder
│   ├── ui/                   # ✅ wired — Chainlit handler drives the outer graph
│   ├── graph/                # ✅ built — LangGraph orchestration (per L10)
│   │                         #    state.py, client.py, prompts.py, logging.py,
│   │                         #    inner.py, outer.py, nodes/{rewrite,decompose,
│   │                         #    intent,retrieve,self_check,generate,refuse,
│   │                         #    citations}.py
│   └── ingest/               # ⬜ not built — OCR + chunking (collaborator owns)
│
├── prompts/                  # ✅ Jinja2 prompt templates, one per node (L19)
├── chroma/                   # persisted vector store (DB files gitignored)
├── Data/Books/               # raw textbook PDFs (gitignored)
├── logs/                     # daily JSONL query records (L18; gitignored)
├── docs/query_pipeline.n8n.json  # legacy n8n prototype — reference only
└── scripts/                  # one-off CLI utilities (e.g. smoke_run.py)
```

**What's built:** `src/retrieval/` (Chroma client + Jina-v4 embedder),
`src/graph/` (the full agentic pipeline per L1–L21), `src/ui/` (Chainlit
handler wired via `astream_events`), `prompts/` (Jinja templates),
`scripts/smoke_run.py` (programmatic end-to-end smoke test). The only
remaining ⬜ is `src/ingest/` (collaborator-owned) and the swap of
`src/graph/nodes/retrieve.py` from its hardcoded-chunks stub to the real
Chroma+rerank impl once ingestion populates the collections.

---

## Two halves of the pipeline

The codebase is split by ownership:

| Half                         | Owner        | Boundary                                                  |
| ---------------------------- | ------------ | --------------------------------------------------------- |
| **Ingestion** (offline)      | collaborator | PDF → OCR → chunk → embed → Chroma (`src/ingest/`)        |
| **Query path** (online)      | Turki        | `retrieve()` → decompose → intent → self-check → generate → cite |

They meet at the **Chunk contract** — the metadata schema locked in `src/retrieval/chroma_client.py:8-18`. Don't redefine those fields elsewhere; import or reference that schema.

Pipeline shape (read top-to-bottom = request flow):

```
Chainlit (src/ui/app.py)
  → graph.outer:  rewrite-history → decompose → [map over tasks]            ← RESPONSE_WORKFLOW L7, L4, L15
                  → graph.inner:   intent → retrieve → self-check
                                   → (generate | refuse) → citations         ← L9, L6, L1, L5
                  → merge
```

Orchestration is **LangGraph** (per L8), not plain LangChain. Inner + outer graphs share state via `TaskState` / `OuterState` (L9). All LLM calls go through a single swappable `LLMClient` (L3, L20) — dev backend is OpenRouter free models, deployment is ALLaM-7B; **never call `transformers` directly from a node.** Prompts are Jinja2 templates in `prompts/*.j2` (L19). The Chainlit handler subscribes to `outer_graph.astream_events(...)` for per-node `cl.Step` cards and token streaming (L21) — graph nodes never import `chainlit`.

---

## Conventions enforced in this repo

- **Grade isolation is structural.** One Chroma collection per grade (`grade_4`, `grade_7`, `grade_10`). Subject is a metadata filter at query time. See `BUILD_SPEC.md §4.3`. Don't add a cross-grade collection or "fallback" search.
- **Refusal is canonical.** When self-check fails, return the exact phrase `لم أجد هذا في الكتاب المدرسي` / `I couldn't find this in your textbook` + parent lesson titles of top-3 chunks. No free generation, no rephrased refusals. See `BUILD_SPEC.md §4.5` and `RESPONSE_WORKFLOW.md L1`.
- **Citations are inline-by-the-model.** ALLaM writes `[n]` markers per claim during generation; the downstream node only **renders** them — it never invents a chunk↔number mapping. See `RESPONSE_WORKFLOW.md L5`.
- **Config in `config.yaml`, secrets in `.env`.** Never hardcode model IDs, base URLs, or temperatures. See `RESPONSE_WORKFLOW.md L17` for the exact shape.
- **Prompts live in `prompts/*.j2`** (one Jinja2 file per node), out of code. See `RESPONSE_WORKFLOW.md` L10, L19.
- **LLM errors retry transient, surface persistent** at the `LLMClient` boundary — 3 tries with exponential jitter for connection/timeout/5xx/rate-limit; 4xx and exhausted retries bubble to the Chainlit handler. See `RESPONSE_WORKFLOW.md L20`.
- **Chainlit ↔ graph wiring is via `astream_events`** — nodes stay pure (no `cl.*` imports). The handler is the only seam. See `RESPONSE_WORKFLOW.md L21`.
- **Every query writes a JSONL record + stdout line** via `src/graph/logging.py` (L18). `logs/` is gitignored.
- **The `agentic-pipeline` branch is where the query-path work happens.** `main` holds only the scaffold + spec.

---

## Commands

This project uses `uv` (not pip). Every command is run from the repo root unless noted.

```bash
# Install / sync deps from the lock file (creates .venv automatically).
uv sync

# (Re)create the empty Chroma collections — idempotent.
uv run python -m src.retrieval.init_chroma

# Launch the Chainlit UI (now wired to the LangGraph outer pipeline).
# Must `cd src/ui` because Chainlit reads chainlit.md, .chainlit/, public/ from CWD.
# PYTHONPATH=../.. keeps `from src...` imports resolvable.
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py)

# Run the agentic pipeline end-to-end without the UI. With
# `llm.backend: fake` in config.yaml this needs no API key (Phase A
# milestone). Flip to `openrouter` + set OPENROUTER_API_KEY for real calls.
uv run python scripts/smoke_run.py "what is photosynthesis?"

# Tail today's query log (JSONL per L18). One line per query.
tail -f "logs/queries-$(date +%F).jsonl"

# Inspect Chroma counts from the CLI.
uv run python -c "from src.retrieval.chroma_client import get_collection; \
                  print({n: get_collection(n).count() for n in (4, 7, 10)})"

# Add a dependency (updates pyproject.toml + uv.lock).
uv add <package>

# Regenerate requirements.txt after a dep bump (pip fallback file).
uv export --format requirements-txt --no-hashes --no-emit-project \
  --output-file requirements.txt
```

### Tests + lint

```bash
# pytest suite (~1.5s, no network, no API key needed; backend forced to
# `fake` by tests/conftest.py). See tests/README.md for layout.
uv run pytest

# A single test file or test
uv run pytest tests/test_citations.py
uv run pytest tests/test_intent.py::test_looks_like_chat_true

# Lint + auto-fix (ruff config lives under [tool.ruff] in pyproject.toml)
uv run ruff check src/ tests/ scripts/
uv run ruff check --fix src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/    # formatter (optional)
```

Both `pytest` and `ruff` should be green before merging.

---

## Working with this repo

- **Read `BUILD_SPEC.md` + `RESPONSE_WORKFLOW.md` before proposing any architectural change.** The decisions in those docs are the output of grilling sessions; revisiting one requires a new grilling round, not an off-the-cuff suggestion.
- **All query-path code lives in `src/graph/`** (state, client, prompts, logging, nodes, inner, outer). Do not move it to `src/agent/` or `src/generation/` — those folders were superseded by L10.
- **The Chroma collections are empty.** `src/graph/nodes/retrieve.py` currently returns hardcoded chunks per L2 — when the ingestion half lands, this is a single-file swap; the metadata schema in `src/retrieval/chroma_client.py:8-18` is the contract.
- **Cuttable features** (per `BUILD_SPEC.md §8` Risk #4): history rewrite (L7), decomposition (L4). Both already respect a `config.yaml` `features.*_enabled` flag and short-circuit to the no-LLM path when off — don't remove that.
- **Every new node wears `@timed("name")`** from `src/graph/logging.py` so its latency surfaces in the L18 record. Decorator merges debug fields, so it's safe to combine with explicit `state.debug` updates inside the node.

---

## Commit policy

- **Do not append a `Co-Authored-By: Claude …` trailer.** The user explicitly rejected it; omit it from every commit.
- Match the existing commit-message style — read recent `git log` before composing. Current style: a short imperative subject, optionally followed by a short body. No emoji prefixes, no scope tags.
- One commit per locked decision or per finished node, not per file edit.
