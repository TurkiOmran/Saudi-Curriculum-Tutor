# `src/graph/` — LangGraph orchestration of the query path

The agentic half of Aleem. Owns the pipeline from a raw user message to a
grounded, cited answer. Decisions live in `RESPONSE_WORKFLOW.md` (L1–L21).

## Files

| File          | What it does                                                                                                                                                                  |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `state.py`    | `Chunk` (mirrors the Chroma metadata schema), `Citation`, `TaskState` (inner-graph state, L9), `OuterState` (outer-graph state), plus `initial_*` constructors.               |
| `client.py`   | `get_llm(temperature=...)` — single factory returning a LangChain `BaseChatModel`. Backend (`fake` / `openrouter` / `ollama`) selected by `config.yaml` (L3, L17, L20).        |
| `nodes/`      | One file per graph node — see `nodes/README.md`.                                                                                                                              |
| `inner.py`    | `inner_graph` — `intent → retrieve → self_check → (generate \| refuse) → citations` (L9). The L1 / L6 routing lives here.                                                     |
| `outer.py`    | `outer_graph` — `rewrite → decompose → map_tasks → merge`. `map_tasks` invokes `inner_graph.ainvoke` in a sequential `for` loop per L15.                                       |

## How to run end-to-end

```bash
# Day-one stub run — no API key, llm.backend: fake in config.yaml
uv run python scripts/smoke_run.py "what is photosynthesis?"

# Real run (Phase B+) — set OPENROUTER_API_KEY in .env and flip
#   llm.backend: openrouter
# in config.yaml.
uv run python scripts/smoke_run.py "what is photosynthesis?"
```

Inner graph in isolation:

```python
import asyncio
from src.graph.inner import inner_graph
from src.graph.state import initial_task_state

task = initial_task_state(grade=7, subject="islamic_studies",
                          standalone_question="what is photosynthesis?",
                          language="en")
result = asyncio.run(inner_graph.ainvoke(task))
print(result["answer"], len(result["citations"]))
```

## Key design points

- **One LLMClient, one config switch (L3).** Nodes never import a specific
  provider. Swap backends by editing `config.yaml` `llm.backend`.
- **Inner / outer split (L9).** Inner runs once per atomic task; outer
  handles session-level concerns (history rewrite, decomposition, merge).
  Subtasks run **sequentially** per L15.
- **Nodes stay pure (L21).** No `cl.*` imports inside nodes. The Chainlit
  UI subscribes to LangGraph events via `outer_graph.astream_events()`,
  so the same graph runs identically in the smoke script, in tests, and in
  any future non-UI caller.
- **Cuttable nodes (Risk #4).** `decompose` and `rewrite` each respect a
  `features.*_enabled` flag in `config.yaml` and bypass the LLM when off.
- **Inline citations (L5).** `generate` writes `[n]` markers; `citations`
  only parses them — it never invents a chunk↔number mapping.
- **Strict refusal (L1).** When self-check fails, `refuse` returns the
  canonical phrase + parent lesson titles of the top-3 chunks. No free
  generation.

## Phase status (build order per the original plan)

- ✅ **Phase A** — scaffold + stubs; graph runs end-to-end without an API key.
- ✅ **Phase B** — OpenRouter LLM client with `Runnable.with_retry` per L20.
- ✅ **Phase C** — real node impls behind a `backend=fake` fallback (intent / self_check / generate / decompose).
- ✅ **Phase D** — Chainlit wired via `astream_events` per L21.
- ✅ **Phase E** — L7 history rewrite + L16 language detection.
- ✅ **Phase F** — L18 JSONL + stdout logging via `@timed` + `log_query`.

## Not here

- Real `retrieve()` — currently a stub returning hardcoded chunks (L2).
  The real `query embed → Chroma top-20 → Jina rerank → top-5` is a
  later task. The stub returns chunks matching the metadata contract in
  `src/retrieval/chroma_client.py:8-18`, so the swap is one file.
- Prompts — `prompts/*.j2`, see `prompts/README.md` (L19).
- The Chainlit UI itself — `src/ui/app.py`.
- Logging — `src/graph/logging.py` lands in Phase F (L18).
