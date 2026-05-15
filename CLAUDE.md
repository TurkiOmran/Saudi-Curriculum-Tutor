# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Aleem is a curriculum-grounded RAG tutor over official Saudi Ministry of Education textbooks. Every answer must be traceable to a specific grade-level textbook chunk; refusal is a first-class outcome. This file is a **map** — it tells you where to look, not how each piece works.

---

## Where to look first

| If you need to…                          | Open                                          |
| ---------------------------------------- | --------------------------------------------- |
| Understand the project pitch / problem   | `README.md`                                   |
| Find a **locked design decision**        | `BUILD_SPEC.md` (numbered sections §1–§10)    |
| Find an **agentic-layer decision** (L1–L18) | `RESPONSE_WORKFLOW.md`                     |
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
│   ├── ui/                   # ✅ scaffolded — Chainlit shell (stub handler)
│   ├── ingest/               # ⬜ not built — OCR + chunking (collaborator owns)
│   ├── agent/                # ⬜ not built — decompose + intent classifier
│   ├── generation/           # ⬜ not built — ALLaM + self-check + refusal
│   └── graph/                # ⬜ not built — LangGraph orchestration (per L10)
│                             #    Planned: state.py, client.py, nodes/, inner.py, outer.py
│
├── chroma/                   # persisted vector store (DB files gitignored)
├── Data/Books/               # raw textbook PDFs (gitignored)
├── docs/query_pipeline.n8n.json  # legacy n8n prototype — reference only
└── scripts/                  # one-off CLI utilities (currently empty)
```

**What's built vs. planned:** the only working code today is `src/retrieval/` (chroma_client, embeddings, init_chroma) and `src/ui/app.py` (UI shell with stub `@cl.on_message`). Everything else listed in `src/` is planned per the task list — do **not** assume files exist; check first.

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

Orchestration is **LangGraph** (per L8), not plain LangChain. Inner + outer graphs share state via `TaskState` / `OuterState` (L9). All LLM calls go through a single swappable `LLMClient` (L3) — dev backend is OpenRouter free models, deployment is ALLaM-7B; **never call `transformers` directly from a node.**

---

## Conventions enforced in this repo

- **Grade isolation is structural.** One Chroma collection per grade (`grade_4`, `grade_7`, `grade_10`). Subject is a metadata filter at query time. See `BUILD_SPEC.md §4.3`. Don't add a cross-grade collection or "fallback" search.
- **Refusal is canonical.** When self-check fails, return the exact phrase `لم أجد هذا في الكتاب المدرسي` / `I couldn't find this in your textbook` + parent lesson titles of top-3 chunks. No free generation, no rephrased refusals. See `BUILD_SPEC.md §4.5` and `RESPONSE_WORKFLOW.md L1`.
- **Citations are inline-by-the-model.** ALLaM writes `[n]` markers per claim during generation; the downstream node only **renders** them — it never invents a chunk↔number mapping. See `RESPONSE_WORKFLOW.md L5`.
- **Config in `config.yaml`, secrets in `.env`.** Never hardcode model IDs, base URLs, or temperatures. See `RESPONSE_WORKFLOW.md L17` for the exact shape.
- **Prompts live in `prompts/`** (one file per node), out of code. See `RESPONSE_WORKFLOW.md L10`.
- **The `agentic-pipeline` branch is where the query-path work happens.** `main` holds only the scaffold + spec.

---

## Commands

This project uses `uv` (not pip). Every command is run from the repo root unless noted.

```bash
# Install / sync deps from the lock file (creates .venv automatically).
uv sync

# (Re)create the empty Chroma collections — idempotent.
uv run python -m src.retrieval.init_chroma

# Launch the Chainlit UI shell.
# Must `cd src/ui` because Chainlit reads chainlit.md, .chainlit/, public/ from CWD.
# PYTHONPATH=../.. keeps `from src.retrieval...` imports resolvable.
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py)

# Inspect Chroma counts from the CLI.
uv run python -c "from src.retrieval.chroma_client import get_collection; \
                  print({n: get_collection(n).count() for n in (4, 7, 10)})"

# Add a dependency (updates pyproject.toml + uv.lock).
uv add <package>

# Regenerate requirements.txt after a dep bump (pip fallback file).
uv export --format requirements-txt --no-hashes --no-emit-project \
  --output-file requirements.txt
```

There is **no test suite, no linter, no formatter configured yet.** Don't fabricate `uv run pytest` / `uv run ruff` commands — they will fail. If you add one, document it here.

---

## Working with this repo

- **Read `BUILD_SPEC.md` + `RESPONSE_WORKFLOW.md` before proposing any architectural change.** The decisions in those docs are the output of grilling sessions; revisiting one requires a new grilling round, not an off-the-cuff suggestion.
- **Don't move code into `src/agent/` or `src/generation/`.** Per `RESPONSE_WORKFLOW.md L10`, all new query-path code goes into `src/graph/` (state, client, nodes, inner, outer). The `agent/` and `generation/` folders listed in the old README are superseded.
- **The Chroma collections are empty.** Until the ingestion half is built, `retrieve()` should be stubbed with hardcoded chunks so the agentic pipeline can be developed end-to-end. See `RESPONSE_WORKFLOW.md L2`.
- **Cuttable features** (per `BUILD_SPEC.md §8` Risk #4): history rewrite (L7), decomposition (L4). Both must be wireable to a no-op via `config.yaml` feature flags — don't build them in a way that can't be turned off.

---

## Commit policy

- **Do not append a `Co-Authored-By: Claude …` trailer.** The user explicitly rejected it; omit it from every commit.
- Match the existing commit-message style — read recent `git log` before composing. Current style: a short imperative subject, optionally followed by a short body. No emoji prefixes, no scope tags.
- One commit per locked decision or per finished node, not per file edit.
