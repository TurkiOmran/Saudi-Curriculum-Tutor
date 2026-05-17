# Aleem

Aleem is a curriculum-grounded RAG tutor over official Saudi Ministry of Education textbooks. Every answer must be traceable to a specific grade-level textbook chunk; refusal is a first-class outcome.

Code lives under `src/` (retrieval, graph orchestration, UI). Each subfolder has a README. Ingestion (OCR + chunking) is not yet in-tree — collaborator owns it.

This project uses `uv` (not pip). See `SETUP.md` for install and run. Run tests with `uv run pytest`; lint with `uv run ruff check src/ tests/ scripts/`. Both must be green before merging.

## Where to look first

| If you need to…                              | Open                                          |
| -------------------------------------------- | --------------------------------------------- |
| Understand the project pitch / problem       | `README.md`                                   |
| Find a locked design decision                | `BUILD_SPEC.md` (numbered sections §1–§10)    |
| Find an agentic-layer decision (L1–L22)      | `RESPONSE_WORKFLOW.md`                        |
| Get the repo running from a fresh clone      | `SETUP.md`                                    |
| Work inside a subfolder                      | That folder's `README.md`                     |

`RESPONSE_WORKFLOW.md` overrides `BUILD_SPEC.md` where they disagree.

## Working in this repo

- `main` is the active branch and contains the built query path (intent → rewrite → decompose → retrieve → self_check → generate, plus the chat intent). The `agentic-pipeline` branch is historical.
- Read `BUILD_SPEC.md` and `RESPONSE_WORKFLOW.md` before proposing any architectural change. Decisions in those docs came out of grilling sessions; revisiting one is a new grilling round, not an off-the-cuff suggestion.
- When a change invalidates something stated in this file or a README, update the doc in the same commit.

## Commits

- Match recent `git log` style: short imperative subject, optional short body, no emoji or scope prefixes.
- One commit per locked decision or per finished node, not per file edit.
- Never append `Co-Authored-By: Claude …`.
