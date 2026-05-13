# `src/ui/` — Chainlit application

The student-facing UI. Currently a **shell**: profile picker, subject
picker, session state, and a stub message handler that confirms the
captured `(grade, subject)` state. No retrieval, no generation.

## Files

| File                          | What it does                                                            |
| ----------------------------- | ----------------------------------------------------------------------- |
| `app.py`                      | Chainlit entrypoint — `@cl.set_chat_profiles`, `@cl.on_chat_start`, `@cl.on_settings_update`, `@cl.on_message`. |
| `chainlit.md`                 | Markdown shown on the Chainlit landing screen (the welcome content).   |
| `.chainlit/config.toml`       | Chainlit config — wires up the custom CSS and sets the app title.       |
| `public/stylesheet.css`       | Arabic font + per-message auto-RTL. See `public/README.md`.             |

## Run

```bash
# from src/ui/  — Chainlit reads chainlit.md, .chainlit/, and public/
# from the current working directory, so we cd in.
# PYTHONPATH=../.. keeps `from src.retrieval...` imports resolvable when
# they're wired in.
cd src/ui
PYTHONPATH=../.. uv run chainlit run app.py
```

Default URL: <http://localhost:8000>.

**Prerequisite:** the Chroma collections must exist. Run
`uv run python -m src.retrieval.init_chroma` (from the repo root) once
before launching, even though the shell doesn't query Chroma yet —
keeps the dev flow consistent.

## What works today

- Landing screen shows three grade cards (Grade 4 / 7 / 10) with bilingual
  descriptions.
- Clicking a card opens a chat with that grade stored in
  `cl.user_session`.
- The settings panel (⚙ gear icon) has a single Subject dropdown with 5
  bilingual options.
- Changing the subject updates `cl.user_session["subject"]`.
- Sending any message returns a placeholder confirming the captured
  `(grade, subject)` — proving the profile + settings flow works.

## What's stubbed

`@cl.on_message` does **not** query Chroma, run an embedder, run Jina
Reranker, or call ALLaM. It returns a fixed placeholder. Once the
retrieval and generation layers land, this handler becomes the orchestration
point:

```
on_message → embed query → Chroma top-20 → Jina Reranker v3 → top-5
           → ALLaM self-check → ALLaM grounded generation → render
```

See `BUILD_SPEC.md §2` for the full target architecture.

## Subject ↔ key mapping

The dropdown shows bilingual labels (e.g. `العربية  ·  Arabic`) but stores
an internal `key` (`"arabic"`) in the session. That key is what the
retrieval layer will eventually pass as a Chroma `where={"subject": key}`
filter, matching the metadata schema in `BUILD_SPEC.md §4.2`.

Keys: `arabic`, `islamic_studies`, `social_studies`, `english`, `math`.

## Not here

- Source-card rendering for citations — added when real retrieved chunks
  exist.
- Streaming of generation tokens — added when ALLaM is wired in.
- Refusal-with-related-lessons UI — added with the generation layer.
