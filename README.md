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

```
User request + grade + subject (Chainlit ChatProfile)
  ↓
Rewrite-history step  ── "quiz me on that" → "quiz me on photosynthesis"
                         (also returns detected language, ar/en)
  ↓
Query decomposition agent  ── splits compound requests
  ↓ for each sub-request:
    Intent classifier  ── {Q&A, explain, summarize, revise, quiz, chat}
    ↓
    ├─ intent == chat  → bounded friendly reply (no retrieve, no grounding)
    │                   greetings, thanks, "what can you do?"
    │
    └─ educational intents:
        Embed query (Jina-v4, retrieval.query mode)
        ↓
        Chroma top-20  (filtered by grade collection + subject metadata)
        ↓
        Jina Reranker v3  → top-5
        ↓
        ALLaM-7B self-check: "Is the answer in these chunks?"
           ├─ no   → refusal + parent lesson titles of top-3 chunks
           └─ yes  → grounded generation with inline [n] citations
  ↓
Merge sub-answers → Chainlit renders with expandable source cards
```

See `RESPONSE_WORKFLOW.md` L1–L22 for the locked decisions behind each step.

---

## Stack

| Layer | Choice |
| --- | --- |
| **OCR** | [Mistral OCR](https://docs.mistral.ai/studio-api/document-processing/basic_ocr/) (`mistral-ocr-latest`) — hosted, Arabic-capable, with image annotation. See `OCR_implementation.md`. |
| **Embeddings** | [jina-embeddings-v4](https://huggingface.co/jinaai/jina-embeddings-v4) — multilingual, multimodal, long-context |
| **Vector store** | [Chroma](https://www.trychroma.com/) — one collection per grade (4, 7, 8, 10) |
| **Reranker** | [jina-reranker-v2-base-multilingual](https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual) — cross-encoder rerank over Chroma top-K |
| **Generator** | [ALLaM-7B-Instruct-preview](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview) — the Saudi national LLM |
| **UI** | [Chainlit](https://chainlit.io/) with RTL Arabic layout |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) |

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
├── RESPONSE_WORKFLOW.md                  ✓  Agentic-layer decisions (L1–L22)
├── SETUP.md                              ✓  Install + run instructions
├── CLAUDE.md                             ✓  Navigational map (for Claude Code sessions)
├── Capstone_Proposal_*.md                ✓  Original proposal (historical)
├── config.yaml                           ✓  Backend-pluggable LLM config (L17)
├── Data/Books/                           ✓  Raw textbook PDFs (gitignored)
├── chroma/                               ✓  Persisted Chroma collections per grade
├── logs/                                 ✓  Daily JSONL query records (L18; gitignored)
├── prompts/                              ✓  6 Jinja prompt templates (L19), one per node
├── scripts/                              ✓  smoke_run.py CLI (programmatic end-to-end)
├── src/
│   ├── retrieval/                        ✓  Jina-v4 embedder + Chroma client
│   ├── ui/                               ✓  Chainlit app wired via astream_events (L21)
│   ├── graph/                            ✓  LangGraph pipeline per RESPONSE_WORKFLOW L10
│   │   ├── state.py / client.py          ✓  State types, LLMClient factory
│   │   ├── prompts.py / logging.py       ✓  Jinja loader, @timed + log_query (L18)
│   │   ├── inner.py / outer.py           ✓  Inner + outer graphs (L9)
│   │   └── nodes/                        ✓  rewrite, decompose, intent, retrieve,
│   │                                            self_check, generate, refuse, citations, chat
│   └── ingest/                           ⬜  OCR + chunking pipeline (collaborator-owned)
├── tests/                                ✓  pytest suite (61 tests, fake backend)
└── eval/                                 ⬜  Smoke + benchmark eval sets
```

> **What's actually stubbed?** Only `src/graph/nodes/retrieve.py` — it
> returns 3 hardcoded chunks until ingestion populates Chroma. Everything
> else along the query path is built.

---

## Getting Started

> **Status:** The full agentic query path (rewrite → decompose → intent →
> retrieve → self-check → (generate | refuse | chat) → citations → merge)
> is built and tested. The only stub left is `retrieve()` — it returns 3
> hardcoded chunks until ingestion populates Chroma. So you can run the
> entire pipeline end-to-end today with **no API key** (`backend: fake`)
> or with a real LLM (`backend: openrouter`, ~$0.001 per query).

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
uv run pytest                                              # 61 tests, ~1.5s
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
