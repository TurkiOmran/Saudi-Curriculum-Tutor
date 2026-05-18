# Agentic Query Pipeline

Turns a student's chat message into a grounded, cited answer drawn only from their grade's textbooks — or a refusal when the textbook can't support an answer.

## Inputs
The student's latest message, the recent chat history, and the session context (grade and subject).

## Two-graph shape
The pipeline is a LangGraph composition of an **outer graph** (handles the whole message) and an **inner graph** (handles one task at a time). Compound messages produce multiple tasks; each task flows through the inner graph sequentially.

## Outer graph stages

1. **Rewrite** — one LLM call rewrites the new message into a standalone question using the chat history (so "quiz me on that" becomes "quiz me on photosynthesis") and also detects the language (Arabic or English) via structured output.
2. **Decompose** — one LLM call splits the standalone question into a list of tasks; a simple question yields a single-item list, a compound question ("summarize and quiz me") yields multiple.
3. **Map over tasks** — each task is sent through the inner graph in order.
4. **Merge** — the per-task answers, citations, and refusal flags are stitched back into one final response.

## Inner graph stages (per task)

5. **Intent classification** — a structured-output LLM call labels the task as one of six intents: `qa`, `explain`, `summarize`, `revise`, `quiz`, or `chat`.
6. **Chat branch (only if intent = chat)** — for greetings, small talk, and meta-questions, a bounded `chat` prompt generates a short reply that never states facts and always invites the student back to the textbook; this branch skips retrieval, self-check, and citations entirely.
7. **Retrieve (educational intents only)** — the task question is embedded with Jina-v4, the top-20 candidate chunks are pulled from the grade-scoped Chroma collection, then reranked with the Jina reranker down to the top-5 most relevant chunks.
8. **Self-check (gates `qa` and `explain` only)** — one strict LLM call asks "based only on these 5 chunks, can the question be fully answered? yes/no"; `summarize`, `revise`, and `quiz` skip this gate and go straight to generation.
9. **Refusal branch (self-check = no)** — the response is the canonical phrase ("I couldn't find this in your textbook" / "لم أجد هذا في الكتاب المدرسي") plus the parent lesson titles of the top-3 chunks framed as "Related topics in your textbook"; no free-generated answer is allowed.
10. **Generation branch (self-check = yes, or non-gated intent)** — the top-5 chunks are handed to the generator LLM pre-numbered (`[1] …`, `[2] …`); the model writes the answer in the student's language and embeds `[n]` markers inline at each claim.
11. **Citations** — the citation node parses the `[n]` markers the model already wrote and renders the matching source chunks as expandable cards at the bottom of the response; no new mapping is invented.

## LLM backend
Every LLM call goes through one swappable `LLMClient` configured by `config.yaml`. Dev backend is OpenRouter (free models with tool-calling support); deployment backend is ALLaM-7B. Swapping is a config change, not a code change.

## Streaming UX
The Chainlit UI consumes LangGraph's `astream_events`: a single ephemeral status message updates as each node fires ("Understanding your question…", "Finding relevant pages…", "Checking the textbook…"), then disappears and the generator's tokens stream into the final answer in real time.

## Logging
Every query writes one JSONL record to `logs/queries-YYYY-MM-DD.jsonl` capturing rewrite output, intent, top-5 reranker scores, self-check verdict, refusal flag, and per-node latency.

## Key properties
- **Grounded**: educational answers cite only retrieved chunks; refusal is a first-class outcome, never a free-generated guess.
- **Grade-scoped**: retrieval always hits the student's own grade collection — no cross-grade leakage.
- **Language-aware**: Arabic and English share the same pipeline; the response language follows the student's query language.
