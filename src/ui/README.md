# `src/ui/` — Chainlit application

The student-facing UI, wired to the LangGraph outer pipeline via
`astream_events` (per L21). Sends per-node `cl.Step` cards while the
pipeline runs, streams answer tokens from the generate node, and attaches
citation source cards to the final message.

## Files

| File                          | What it does                                                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `app.py`                      | Chainlit entrypoint — chat profiles, settings panel, **and** the `@cl.on_message` handler that drives the outer graph. |
| `chainlit.md`                 | Markdown shown on the Chainlit landing screen (the welcome content).                                              |
| `.chainlit/config.toml`       | Chainlit config — wires up the custom CSS and sets the app title.                                                  |
| `public/stylesheet.css`       | Arabic font + per-message auto-RTL. See `public/README.md`.                                                        |

## Run

```bash
cd src/ui
PYTHONPATH=../.. uv run chainlit run app.py
```

Default URL: <http://localhost:8000>.

The Chroma collections must exist (`uv run python -m src.retrieval.init_chroma`
from the repo root) before launching. With `llm.backend: fake` in
`config.yaml` you don't need an API key — the pipeline runs end-to-end on
hardcoded chunks and a canned LLM stub. Flip to `openrouter` (and set
`OPENROUTER_API_KEY` in `.env`) for real generation.

## What works today

- Landing screen — four grade cards (Grade 4 / 7 / 8 / 10) with bilingual
  descriptions.
- Settings panel (⚙) — subject dropdown with five bilingual options.
- `@cl.on_message` drives the full outer graph
  (`rewrite → decompose → map_tasks → merge`) and renders each stage as
  a `cl.Step` card in the chat: "Understanding your question…", "Finding
  relevant pages…", "Checking the textbook…", "Composing answer…",
  "Resolving citations…", etc.
- **Token streaming** from the generate node — answer tokens stream into
  a Chainlit message as the LLM emits them, per L11.
- **Citation cards** — every `[n]` marker in the answer surfaces as an
  expandable `cl.Text` element with chunk text + lesson title + page.
- **Refusal path** (L1) — when self-check returns false, the canonical
  phrase + related lesson titles render without any free generation.
- **Session history** — last `memory.max_turns × 2` turns kept in
  `cl.user_session["history"]` for the L7 rewrite node (Phase E).

## How the UI ↔ graph plumbing works (L21)

The handler subscribes to `outer_graph.astream_events(state, version="v2")`
and routes events:

| LangGraph event              | Chainlit primitive             | Notes                                                            |
| ---------------------------- | ------------------------------ | ---------------------------------------------------------------- |
| `on_chain_start` (node)      | `cl.Step(name=NODE_LABELS[…])` | Sent at start; sole nodes shown are listed in `app.NODE_LABELS`. |
| `on_chain_end`   (node)      | `step.update()`                | Closes the step card.                                            |
| `on_chat_model_stream`       | `msg.stream_token(token)`      | Filtered by `metadata.langgraph_node == "generate"`.             |
| `on_chain_end`   (root)      | capture `data.output`          | Source for `final_answer` and citation rendering.                |
| any exception                | `cl.Message("⚠️ Pipeline …")` | L20 — surfaces persistent failures with a visible error card.    |

Graph nodes themselves never import Chainlit. This file is the only seam.

## Subject ↔ key mapping

The dropdown shows bilingual labels (e.g. `العربية  ·  Arabic`) but stores
an internal `key` (`"arabic"`) in the session. That key is what the
retrieval layer passes as a Chroma `where={"subject": key}` filter,
matching the metadata schema in `BUILD_SPEC.md §4.2`.

Keys: `arabic`, `islamic_studies`, `social_studies`, `english`, `math`.

## Not here

- Graph definitions — `src/graph/inner.py`, `src/graph/outer.py`.
- LLM client + retry — `src/graph/client.py`.
- Prompt templates — `prompts/*.j2`.
- Query logging — `src/graph/logging.py` (Phase F).
