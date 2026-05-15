# `src/graph/nodes/` — one file per graph node

Each node is an `async def` taking the current state and returning a
**partial** state-update dict (LangGraph merges it back in). No node imports
Chainlit (per L21); observability is via `astream_events` from the UI layer.

## Files

| Node           | Graph | Phase A behavior                                                                                  | Phase C / E target                                                                            |
| -------------- | ----- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `rewrite.py`   | outer | Passthrough — language detected by regex fallback (L16 fallback path).                             | Phase E: structured-output LLM call producing `{standalone_question, language}` over history. |
| `decompose.py` | outer | Returns `[standalone_question]` (single task).                                                     | Phase C: structured-output LLM call producing `list[str]`. Bypassed via L4 feature flag.      |
| `intent.py`    | inner | Returns `"qa"`.                                                                                    | Phase C: `llm.with_structured_output(IntentDecision)` per L13.                                |
| `retrieve.py`  | inner | Returns 3 hardcoded `Chunk` objects (L2 stub).                                                     | Later task: `query embed → Chroma top-20 → Jina rerank → top-5`.                              |
| `self_check.py`| inner | Always `passed=True`. Already implements the L6 skip for `summarize/revise/quiz`.                  | Phase C: strict ALLaM/OpenRouter call over all 5 chunks.                                      |
| `generate.py`  | inner | Returns canned answer with `[1]` marker so `citations` has something to parse.                     | Phase C: per-intent Jinja prompt (L19), streamed via `llm.astream`.                           |
| `refuse.py`    | inner | **Already final.** Pure Python — canonical phrase (L1) keyed off `state.language` + lesson titles. | (unchanged)                                                                                    |
| `citations.py` | inner | **Already final.** Regex-parses `[n]` markers, attaches the matching `Chunk` (L5). No retry (L14).| (unchanged — retry deferred until §6.2 eval shows breakage)                                    |

## Conventions

- **Signature**: `async def <name>_node(state: TaskState | OuterState) -> dict`.
- **Returns** the *partial* update only — keys you didn't set are unchanged.
- **Don't import Chainlit.** Anything UI-facing happens in `src/ui/app.py`
  via LangGraph events.
- **Use `dict(state.get("debug") or {})`** before adding debug keys —
  Python doesn't auto-merge dict updates the way LangGraph merges top-level
  state keys.
- **No LLM in Phase A.** Phase-A stubs return canned values directly.
  Switching them to real LLM calls happens in Phase C without touching
  `inner.py` / `outer.py`.

## Not here

- The graphs themselves — `src/graph/inner.py` and `src/graph/outer.py`.
- Prompt templates — `prompts/*.j2`.
- LLM factory — `src/graph/client.py`.
