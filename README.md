# Aleem — عليم

**A curriculum-grounded RAG tutor for Saudi school students.**

Aleem ("knowledgeable" in Arabic) is an AI tutor that answers student questions using *only* the content of their official Saudi Ministry of Education textbooks. Every answer is traceable to a specific lesson and page in the student's grade-level book — no foreign curriculum content, no hallucinations, no second-guessing what will show up on the exam.

---

## The Problem

Saudi students who use general-purpose LLMs (ChatGPT, Gemini, Copilot) for homework get answers that are *plausible* but *misaligned* with their official curriculum:

- Different terminology than their textbook uses.
- Examples drawn from foreign curricula.
- Material from the wrong grade level.

This forces students to second-guess every answer and risks them memorizing content that will be marked wrong on national exams.

**Aleem's contract:** if the answer isn't in your textbook, the system says so — instead of inventing one.

---

## What Makes Aleem Different

| Feature | Why it matters |
| --- | --- |
| **Grade-isolated retrieval** | A Grade 4 student is *structurally* incapable of receiving Grade 10 content. Each grade has its own vector index. |
| **Curriculum-grounded by construction** | The corpus is *only* official MoE textbooks downloaded from [ien.edu.sa](https://ien.edu.sa). Nothing else. |
| **Lesson-level citations** | Every answer carries inline `[n]` markers linking to the exact lesson, page, and passage. |
| **Refusal as a feature** | When the textbook doesn't cover the question, the system politely refuses and surfaces related lessons from the student's grade. |
| **Bilingual (Arabic + English)** | Designed for both Arabic-medium subjects and the English curriculum. |
| **Saudi model for Saudi content** | Generation runs on **ALLaM**, the Saudi national LLM, trained natively on Arabic. |

---

## Architecture

Aleem uses **one tool-calling agent + one tool + two post-hoc safety
layers**. The shape is locked in `docs/WORKFLOW_SANDBOX.md` (merged from
`workflow-sandbox` in commit `f20595a`).

```
User request + grade + subject (Chainlit ChatProfile)  +  chat history
  ↓
Tool-calling agent  (LangGraph create_react_agent, looped)
  • System prompt: tutor over Saudi MoE textbooks; cite every claim [n];
    answer ONLY from chunks; resolve references from history; use topic
    terms for retrieval; read relevance scores; refuse in own voice if
    chunks don't cover the question.
  • Tool: retrieve(query) → Chroma top-20 → Jina rerank top-5
                          → "[n] (relevance: 0.94) ..."
  • Budget: max 4 retrieve calls per turn
  ↓
Streamed answer with inline [n] markers
  ↓
Layer 2: Citation parse  ── structural: out-of-range [n]? missing
                            citations? Flagged in the log; never repaired.
  ↓
Layer 3: Topical verifier  ── one cheap structured-output LLM call
                              ("is this answer about a topic the chunks
                              actually discuss?"). Default-on; on
                              off_topic → refuse immediately in the
                              agent's voice + topic suggestions.
  ↓
Chainlit renders the answer + side citation cards
  ↓
L18 JSONL log: tool calls, citation flags, verifier verdict,
               rerank scores, latency
```

See `docs/WORKFLOW_SANDBOX.md` (§3 diagram, §4 safety model, §12 eval bar) for
the full design. `RESPONSE_WORKFLOW.md` (L1–L22) describes the older
multi-stage pipeline that motivated the new shape — preserved as the
historical comparison baseline.

---

## Stack

| Layer | Choice |
| --- | --- |
| **OCR** | [Mistral OCR](https://docs.mistral.ai/studio-api/document-processing/basic_ocr/) (`mistral-ocr-latest`) — hosted, Arabic-capable, with image annotation. See `OCR_implementation.md`. |
| **Embeddings** | [jina-embeddings-v4](https://huggingface.co/jinaai/jina-embeddings-v4) — multilingual, multimodal, long-context |
| **Vector store** | [Chroma](https://www.trychroma.com/) — one collection per grade (4, 7, 8, 10) |
| **Reranker** | [jina-reranker-v2-base-multilingual](https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual) — cross-encoder rerank over Chroma top-K |
| **Generator** | [ALLaM-7B-Instruct-preview](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview) — the Saudi national LLM |
| **UI** | [Chainlit](https://chainlit.io/) with RTL Arabic layout — left sidebar lists past chats; transcripts persist locally in SQLite across browser refreshes |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) — `create_react_agent`; `RESPONSE_WORKFLOW.md` preserves the earlier 2-graph design |

---

## Pilot Scope

| Stage | Grade |
| --- | --- |
| Elementary | Grade 4 |
| Middle | Grades 7 and 8 |
| High School | Grade 10 |

**Subjects:** Arabic, Islamic studies, social studies, English, Math (Math conditional on OCR quality validation).

**Corpus size:** ~15 textbooks, ~3,000–4,500 pages, ~5,000–20,000 chunks after structure-aware chunking.

**Out of scope (for now):** diagram understanding, equation LaTeX rendering, multi-tenant user accounts. Documented as future work.

---

## Data

- **Source:** Official Saudi Ministry of Education textbooks from the IEN national educational portal (https://ien.edu.sa) and the MoE website (https://moe.gov.sa).
- **Author:** Ministry of Education, Kingdom of Saudi Arabia.
- **License:** Issued by MoE for educational use. This project uses the materials strictly for non-commercial academic research and does not redistribute the raw textbooks.
- **Languages:** Arabic (majority) and English.
- **Modalities:** Mix of digital-text PDFs and scanned page images (OCR routed per page).

---

## Evaluation

### Demo-phase smoke set (60 questions)

- 70% authored from end-of-chapter exercises (gold answer + source page).
- 20% **should-refuse** off-curriculum questions to verify refusal behavior.
- 10% adversarial bilingual cases.

### Metrics

- **Retrieval:** Recall@5 — did the gold source chunk appear in the top-5 reranked results?
- **Refusal:** Precision and recall on the should-refuse subset.
- **Faithfulness:** Manual review of generated answers — do all claims trace to retrieved chunks?

### Benchmark phase (post-demo)

- 150–300-question gold set, published as a HuggingFace dataset.
- Embedding bake-off (Jina-v4 vs BGE-M3 vs Multilingual-E5 vs Arabic-Triplet-Matryoshka).
- Generator comparison (ALLaM vs Claude vs Gemini).
- Full RAGAS suite: faithfulness, answer correctness, context precision.

---

## Repository Structure

`✓` = built and working, `⬜` = planned (not yet built).

```
.
├── README.md                             ✓
├── BUILD_SPEC.md                         ✓  Locked design decisions (§1–§10)
├── RESPONSE_WORKFLOW.md                  ✓  Historical pipeline decisions (L1–L22)
├── docs/WORKFLOW_SANDBOX.md              ✓  Current tool-calling agent spec
├── SETUP.md                              ✓  Install + run instructions
├── AGENTS.md (CLAUDE.md → AGENTS.md)     ✓  Navigational map (for Claude Code sessions)
├── Capstone_Proposal_*.md                ✓  Original proposal (historical)
├── config.yaml                           ✓  Backend-pluggable LLM + agent + verifier config
├── Data/Books/                           ✓  Raw textbook PDFs (gitignored)
├── chroma/                               ✓  Persisted Chroma collections per grade
├── logs/                                 ✓  Daily JSONL query records (gitignored)
├── prompts/                              ✓  2 Jinja templates: agent.j2 + verifier.j2
├── scripts/                              ✓  smoke_run.py (programmatic agent end-to-end)
├── src/
│   ├── retrieval/                        ✓  Jina-v4 embedder + Chroma client
│   ├── ui/                               ✓  Chainlit app — tool-call cards + token stream
│   ├── graph/                            ✓  Tool-calling agent (WORKFLOW_SANDBOX §3)
│   │   ├── state.py                      ✓  AgentState, Chunk, Citation, ToolCallRecord
│   │   ├── client.py                     ✓  get_llm (+ for_agent=True) and get_verifier_llm
│   │   ├── tools.py                      ✓  @tool retrieve(query) + per-request contextvars
│   │   ├── agent.py                      ✓  create_react_agent + run_agent + finalize
│   │   ├── verifier.py                   ✓  VerifierDecision + verify_topical
│   │   ├── parse.py                      ✓  [n] parse + structural flags
│   │   ├── prompts.py                    ✓  Jinja loader (render / render_pair)
│   │   └── logging.py                    ✓  @timed + log_query (JSONL)
│   └── ingest/                           ✓  OCR + chunking pipeline (collaborator-owned)
└── tests/                                ✓  pytest suite (65 tests, fake backend)
```

> **What's actually stubbed?** Only `src/graph/tools.py`'s
> `_STUB_CHUNKS` fallback — it returns 3 hardcoded chunks when the
> grade's Chroma collection is empty (the test default). Everything
> else along the agent path is built.

---

## Getting Started

> **Status:** The tool-calling agent path (agent loop → retrieve →
> citation parse → topical verifier) is built and tested. The only stub
> left is `retrieve()`'s fallback — it returns 3 hardcoded chunks when
> the per-grade Chroma collection is empty. So you can run the entire
> pipeline end-to-end today with **no API key** (`backend: fake`, the
> shipped default in `config.yaml`) or with a real LLM (`backend:
> openrouter`, ~$0.001 per query).

### Prerequisites

- Python 3.11 (`uv` will install it for you).
- `uv` package manager — `brew install uv` or the one-line installer.
- (Optional) `OPENROUTER_API_KEY` for real LLM answers. Without it the
  pipeline still runs end-to-end with canned replies.
- (Optional, later) Cloud GPU for the production ALLaM-7B deployment.

### Quick start

```bash
git clone <repo-url> Aleem && cd Aleem
uv sync                                                    # install deps
cp .env.example .env                                       # optional keys
uv run python -m src.retrieval.init_chroma                 # create collections
uv run python scripts/smoke_run.py "what is photosynthesis?"   # no UI, no API key
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py)     # browser UI at :8000
uv run pytest                                              # 65 tests, ~4s
```

Full step-by-step in [`SETUP.md`](SETUP.md), including how to switch
backends, troubleshoot rate limits, and tail the JSONL query log.

---

## Roadmap

- [ ] **Phase 1 — Demo (2 weeks):** end-to-end working Chainlit app over Grades 4 / 7 / 10, 5 subjects, with grade-isolated retrieval, lesson-level citations, and refusal handling.
- [ ] **Phase 2 — Benchmark:** publish the 150–300-question Saudi-curriculum eval set as a HuggingFace dataset; run an embedding and generator bake-off.
- [ ] **Phase 3 — Multimodal:** use Jina-v4 image embeddings to retrieve textbook diagrams; route math equations through a LaTeX-aware OCR fallback.
- [ ] **Phase 4 — Pilot:** classroom user testing with a Saudi school.

---

## Team

Capstone project for the **Applied AI Bootcamp**. Built by a team of 2.

---

## License & Use

- **Code:** to be decided (likely MIT or Apache 2.0).
- **Textbook content:** Ministry of Education, Kingdom of Saudi Arabia. Used here strictly for non-commercial academic research under the MoE's educational-use terms. Not redistributed.
- Any deployment beyond this capstone requires explicit permission from the Ministry of Education.

---

## Acknowledgments

- Ministry of Education, Kingdom of Saudi Arabia — official textbook source.
- [Mistral AI](https://mistral.ai/) for the hosted OCR API powering the ingestion pipeline.
- [HUMAIN](https://huggingface.co/humain-ai) / [SDAIA](https://sdaia.gov.sa/) for ALLaM, the Saudi national LLM.
- [Jina AI](https://jina.ai/) for the embedding and reranker models.
- The Applied AI Bootcamp instructors and cohort.
