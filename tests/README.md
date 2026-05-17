# `tests/` — pytest suite

Critical-path coverage for the agentic pipeline and the ingest pipeline.
**All tests run against `backend=fake` and a mocked Mistral client** —
no network, no API key, no token spend. The `_force_fake_backend`
autouse fixture in `conftest.py` rewrites `src.config.settings` for
every test, so a developer with a live `backend: openrouter` in
`config.yaml` still gets fully deterministic runs.

## Files

| File                   | Covers                                                                                    |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| `conftest.py`          | `_force_fake_backend` autouse fixture; `make_task_state` / `make_outer_state` factories.  |
| `test_state.py`        | `Chunk` round-trip, `initial_task_state` / `initial_outer_state` defaults + history.      |
| `test_citations.py`    | L5 / L14 — `[n]` regex parse, dedup, out-of-range, refused short-circuit.                 |
| `test_refuse.py`       | L1 — EN + AR canonical phrase, lesson-title dedup, top-3 cap.                             |
| `test_rewrite.py`      | L7 / L16 — `detect_language_fallback`, fake passthrough.                                  |
| `test_intent.py`       | L13 — fake default, chat-heuristic (en + ar), schema validation.                          |
| `test_self_check.py`   | L6 — `summarize`/`revise`/`quiz`/`chat` skip the gate; `qa`/`explain` get checked.        |
| `test_decompose.py`    | L4 — feature-flag bypass (no LLM), history propagation to TaskStates.                     |
| `test_chat.py`         | L22 — fake bilingual canned reply, no `[n]` citations in chat answers.                    |
| `test_prompts.py`      | L19 — Jinja template renders, intent + language branches.                                 |
| `test_logging.py`      | L18 — `@timed` decorator merges `latency_ms`, `log_query` JSONL record shape.             |
| `test_inner_graph.py`  | L9 — qa happy path, refusal path, chat path bypasses retrieve.                            |
| `test_outer_graph.py`  | L9 — single-task happy path, JSONL written by merge, L16 Arabic detection, L7 history.    |
| `test_ingest_types.py` | `Chunk` / `IngestResult` frozen invariants.                                               |
| `test_ingest_chunk.py` | D6–D9 — page-based chunks, blank-page skip, image-annotation inline, deterministic IDs. Runs against the captured K05 fixture. |
| `test_ingest_load.py`  | D10–D11 — delete-by-`book_id`, batched `add`, empty-chunks guard. Fake Chroma collection. |
| `test_ingest_ocr.py`   | D3 / D12 — atomic write, SHA-256 hash, 4xx denylist (incl. 429-stays-retryable), upload cache, OCR cache, hash-mismatch invalidation, `annotate_images` pass-through. Fake Mistral client. |
| `test_ingest_cli.py`   | D13 — `--grade` choices restricted to `(4, 7, 8, 10)`, `--subject` validated, `--pages` parser. |
| `fixtures/`            | Real Mistral OCR output captured from the validation probe — see `fixtures/README.md`.    |

## Run

```bash
# Full suite (≈1.5s, no network)
uv run pytest

# A single test file
uv run pytest tests/test_citations.py

# A single test
uv run pytest tests/test_intent.py::test_looks_like_chat_true

# Verbose with print output
uv run pytest -vv -s
```

## Coverage philosophy

Critical-path only — every locked decision (L1–L22) has at least one
test that locks its behavior. Edge-case parametrize tables and live
OpenRouter integration tests are deliberately out of scope: they slow
the loop and add flakiness without changing merge-readiness.

If a future decision lands (e.g. L23+), add the matching test alongside
the implementation.

## Not here

- Live OpenRouter / Ollama tests — would require an API key and burn
  tokens on every run. Verify manually via Chainlit or
  `scripts/smoke_run.py`.
- UI / Chainlit tests — `cl.Message` / `cl.Step` mocking isn't worth
  the brittleness for this project. The handler is exercised
  end-to-end during demo runs.
- Coverage reports — add when CI lands, not before.
