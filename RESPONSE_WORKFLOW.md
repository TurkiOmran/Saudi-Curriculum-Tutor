# Response Workflow — Agentic + Generation Layer

Working notes for the LLM/agentic half of Aleem (decomposition → intent → self-check → generation → citations).
Owner: Turki. Embedding/retrieval layer: collaborator.

This doc tracks decisions as we grill them. Locked items build to; open items are still being argued.

---

## Scope of this branch

In scope (Turki):
- `retrieve()` — query embed → Chroma top-20 → Jina rerank top-5 (the full query path)
- Query decomposition agent
- Intent classifier
- ALLaM self-check (refusal gate)
- Grounded generation per intent
- Citation assembly
- Sub-answer merge

Out of scope (collaborator): ingestion only — parse books → MD → chunk → embed → populate Chroma.

The two halves meet at the **Chunk contract** (see L2).

---

## Locked decisions

### L1 — Refusal path does NOT free-generate
When self-check returns "no", the response is:
1. Canonical phrase: `لم أجد هذا في الكتاب المدرسي` / `I couldn't find this in your textbook`
2. Parent lesson titles of the top-3 retrieved chunks, framed as "Related topics in your textbook"

No ungrounded ALLaM answer. The diagram's "try to answer it on your own" is rejected — it breaks the §4.4 grounding contract and risks confident hallucination to students. Matches BUILD_SPEC §4.5.

---

### L2 — Turki owns the full query path, including rerank
`retrieve(query, grade, subject) -> list[Chunk]` does query embed → Chroma top-20 →
Jina reranker → top-5. Collaborator's scope stays at ingestion only. Build against a
**stub** first (hardcoded chunks) so the agentic pipeline runs while Chroma is empty.

**Chunk contract** — the metadata schema is already locked in
`src/retrieval/chroma_client.py` lines 8-18:
`{grade, subject, book, chapter, lesson_title, page, content_type}`.
`lesson_title` is present → refusal path (L1) is safe.

---

## Project state (explored 2026-05-15)

Exists: `src/retrieval/` (chroma_client, embeddings — Jina-v4, init_chroma),
`src/ui/app.py` (Chainlit shell, not wired). Chroma collections created but **empty**.

Missing — all of Turki's scope: query-time retrieve+rerank, ALLaM wrapper,
decomposition, intent classifier, self-check, generation, citations.

---

### L3 — All LLM calls go through one swappable client, configured by file
Every node (decomposition, intent, self-check, generation) calls a single
`LLMClient.complete(system, user, ...)` interface — never `transformers` directly.

- **Dev backend:** OpenRouter free models.
- **Deployment backend:** ALLaM-7B (cloud GPU) — decided later, swap with no code change.
- Model id, base url, api key, temperature etc. live in a **config file** (not hardcoded,
  not scattered). One place to change the backend.

---

### L4 — `decompose()` always runs, always returns a list of tasks
One LLM call at the top of the pipeline. Output is always `list[Task]`:
- single-task query → `[query]` (the default case)
- compound query ("summarize and quiz me") → `[task1, task2]`

Downstream always loops over the list via `run_one()` (intent → retrieve → self-check
→ generate → cite), then `merge()` combines results (trivial passthrough when len==1).

`run_one()` is the critical path — built and hardened first. `decompose()` + `merge()`
are a thin wrapper. A **config flag** can force `decompose()` to return `[query]`
without calling the LLM — the cut-it escape hatch for §8 risk #4.

---

### L5 — Citations are produced inline by ALLaM, only rendered downstream
Chunks are handed to ALLaM pre-numbered (`[1] ...`, `[2] ...`). ALLaM writes the
`[n]` markers inline per claim as it generates. The downstream "citations" node does
**not** invent any mapping — it parses the `[n]` markers ALLaM already wrote and
renders the matching sources as expandable cards **at the bottom** of the response.

Format retries (§4.4): if ALLaM emits an out-of-range `[n]` or no citations, re-prompt.
**Recommended fallback (not yet confirmed by Turki):** after 2 failed retries, show the
answer with a small "sources couldn't be verified" note rather than refusing.

---

### L6 — Self-check uses the strict bar, and only gates Q&A / explain
One ALLaM call over all 5 reranked chunks together. The question is strict:
*"Based only on these chunks, can the student's question be fully answered? yes/no."*
Not the loose "is this relevant" bar — loose lets ALLaM fill gaps by inventing.

Self-check only gates **Q&A** and **explain** intents. For **summarize / quiz / revise**,
if retrieval returned chunks at all, proceed straight to generation (no "answer" to
check for). Per §4.5: log the verdict + the 5 reranker scores for every query.

---

### L7 — Chat memory via query-rewrite (standalone-question) prefix
Keep the last few turns of conversation. Before `decompose()`, one cheap LLM call
rewrites the new user message into a self-contained question using the history
("quiz me on that" → "quiz me on photosynthesis").

Everything downstream (decompose, intent, retrieve, ...) is unchanged — it always
receives a standalone question. Built **last**, after `run_one()` and decomposition.
Cuttable prefix node if week 2 is tight.

This is the real meaning of "Extract session + user query" in the diagram: session
= app settings (grade/subject) **plus** recent chat history.

---

### L8 — Orchestration is LangGraph
The pipeline is a graph: a per-task loop, a self-check branch (yes → generate,
no → refuse), and shared state across nodes. LangGraph fits box-for-box; plain LCEL
LangChain would fight the branch. Spec §3 updated from "LangChain" to "LangGraph".

---

### L9 — Two graphs, shared state, debug dict
**Outer graph:** rewrite-question → decompose → (map inner graph over tasks) → merge.
Outer state holds `list[TaskState]` + final merged answer.

**Inner graph** (`run_one`, over `TaskState`): intent → retrieve → self-check → generate
→ resolve-citations. Retrieve runs per task (subtasks can be different topics).
Decompose output per task is a clean topical question — intent verb not baked in.

`TaskState` fields: `grade, subject, standalone_question` (inputs); `intent, chunks,
self_check_passed, answer, citations, refused` (filled by nodes); `debug: dict`
(reranker scores + self-check verdict per §4.5, dumped once at the end).

---

### L10 — Module layout and branch
Branch: `agentic-pipeline`. Code lives under `src/graph/`:

```
src/graph/state.py        TaskState, OuterState, Chunk
src/graph/client.py       LLMClient — OpenRouter backend (L3)
src/graph/nodes/*.py      one file per node (rewrite, decompose, intent,
                          retrieve, self_check, generate, refuse, citations)
src/graph/inner.py        inner graph (run_one)
src/graph/outer.py        outer graph (decompose / map / merge)
src/config.py             loads config.yaml
config.yaml               model id, base url, feature flags (in-repo)
prompts/                  prompt templates, one per node, out of code
```
Secrets via `.env`. Day-one: all nodes are stubs, `retrieve()` returns hardcoded
chunks, graph runs end-to-end without an API key.

---

## Open questions / still to grill

- Retry fallback when ALLaM keeps breaking citation format (L5) — recommendation logged, not confirmed
- Intent classifier structured-output format (JSON? bare label?) — not yet grilled
- Streaming vs the self-check gate — can't stream until self-check passes; UX detail, not yet grilled
- `teacher-support` intent — in spec's intent list but not in diagram's notes; behavior undefined

---

## Diagram vs. spec — known gaps to resolve

- [x] Refusal path — RESOLVED (L1)
- [x] Citations as post-gen step → RESOLVED (L5): inline `[n]` during generation, downstream only renders
- [x] "Merge sub-answers" missing from diagram → RESOLVED (L9): outer graph merge node
- [ ] Query-language detection / "respond in user's query language" — handled inside generate prompt; not a separate node
- [x] Format retries → RESOLVED (L5): live in the citations-resolve node
