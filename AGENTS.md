# Aleem

Aleem is a curriculum-grounded RAG tutor over official Saudi Ministry of Education textbooks. Every answer must be traceable to a specific grade-level textbook chunk; refusal is a first-class outcome.

Code lives under `src/` (retrieval, graph orchestration, UI, ingestion). Each subfolder has a README. The ingest pipeline (`src/ingest/`) drives Mistral OCR → page-chunking → Jina-v4 embedding → Chroma; design locked in `OCR_implementation.md`.

This project uses `uv` (not pip). See `SETUP.md` for install and run. Run tests with `uv run pytest`; lint with `uv run ruff check src/ tests/ scripts/`. Both must be green before merging.

## Where to look first

| If you need to…                              | Open                                          |
| -------------------------------------------- | --------------------------------------------- |
| Understand the project pitch / problem       | `README.md`                                   |
| Find a locked design decision                | `BUILD_SPEC.md` (numbered sections §1–§10)    |
| Find an agentic-layer decision (L1–L22)      | `RESPONSE_WORKFLOW.md`                        |
| Find the workflow-sandbox agent spec         | `docs/docs/WORKFLOW_SANDBOX.md`                         |
| Get the repo running from a fresh clone      | `SETUP.md`                                    |
| Work inside a subfolder                      | That folder's `README.md`                     |

Precedence when they disagree: `docs/docs/WORKFLOW_SANDBOX.md` (this branch only) > `RESPONSE_WORKFLOW.md` > `BUILD_SPEC.md`.

## Working in this repo

- **You are on `workflow-sandbox`.** This branch replaces the two-graph LangGraph pipeline in `src/graph/` with a single tool-calling agent + topical verifier per `docs/docs/WORKFLOW_SANDBOX.md`. `main` still has the L1–L22 multi-stage pipeline; the merge decision is gated on eval (§12).
- The agent entry point is `src/graph/agent.py::run_agent`. The single tool is `src/graph/tools.py::retrieve`. Post-hoc safety is `src/graph/parse.py` + `src/graph/verifier.py`. The Chainlit UI in `src/ui/app.py` drives the agent via `astream_events` so tool calls surface as "Searching: …" cards.
- Read `BUILD_SPEC.md`, `RESPONSE_WORKFLOW.md`, AND `docs/docs/WORKFLOW_SANDBOX.md` before proposing any architectural change. Decisions in those docs came out of grilling sessions; revisiting one is a new grilling round, not an off-the-cuff suggestion.
- When a change invalidates something stated in this file or a README, update the doc in the same commit.

## Commits

- Match recent `git log` style: short imperative subject, optional short body, no emoji or scope prefixes.
- One commit per locked decision or per finished node, not per file edit.
- Never append `Co-Authored-By: Claude …`.
