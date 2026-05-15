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
                         (also returns detected language)
  ↓
Query decomposition agent  ── splits compound requests
  ↓ for each sub-request:
    Intent classifier  ── {Q&A, explain, summarize, revise, quiz}
    ↓
    Embed query  (Jina-v4, retrieval.query mode)
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

---

## Stack

| Layer | Choice |
| --- | --- |
| **OCR** | [Qari-OCR-0.4.0-VL-4B-Instruct](https://huggingface.co/NAMAA-Space/Qari-OCR-0.4.0-VL-4B-Instruct) — Arabic-specialized vision OCR |
| **Embeddings** | [jina-embeddings-v4](https://huggingface.co/jinaai/jina-embeddings-v4) — multilingual, multimodal, long-context |
| **Vector store** | [Chroma](https://www.trychroma.com/) — one collection per grade |
| **Reranker** | Jina Reranker v3 |
| **Generator** | [ALLaM-7B-Instruct-preview](https://huggingface.co/humain-ai/ALLaM-7B-Instruct-preview) — the Saudi national LLM |
| **UI** | [Chainlit](https://chainlit.io/) with RTL Arabic layout |
| **Orchestration** | [LangGraph](https://langchain-ai.github.io/langgraph/) |

---

## Pilot Scope

| Stage | Grade |
| --- | --- |
| Elementary | Grade 4 |
| Middle | Grade 7 |
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

## Repository Structure (planned)

```
.
├── README.md
├── BUILD_SPEC.md              # Locked design decisions
├── Capstone_Proposal_*.md     # Original proposal
├── data/
│   ├── raw/                   # Downloaded PDFs (gitignored)
│   ├── ocr/                   # Per-book OCR output
│   └── chunks/                # Structure-aware chunks + metadata
├── chroma/                    # Persisted Chroma collections per grade
├── eval/
│   └── smoke_60.jsonl         # 60-question smoke eval set
├── src/
│   ├── ingest/                # OCR + chunking pipeline
│   ├── retrieval/             # Embedding, indexing, reranker
│   ├── graph/                 # Agentic + generation pipeline (LangGraph)
│   │   ├── nodes/             # one file per node: rewrite, decompose, intent,
│   │   │                      #   retrieve, self_check, generate, refuse, citations
│   │   ├── inner.py           # inner graph (run_one per sub-task)
│   │   └── outer.py           # outer graph (decompose / map / merge)
│   └── ui/                    # Chainlit app
├── prompts/                   # Prompt templates, one per node, kept out of code
├── config.yaml                # Backend-pluggable LLM config (OpenRouter / Ollama)
└── scripts/                   # One-off CLI utilities
```

---

## Getting Started

> **Status:** Active development — see `BUILD_SPEC.md` for the locked design and task list.

### Prerequisites
- Python 3.11+
- A GPU with ≥24 GB VRAM (or a cloud GPU on Modal / Runpod / Lambda) for ALLaM-7B + Jina-v4 + Jina Reranker.
- Access to the Saudi MoE textbook PDFs from [ien.edu.sa](https://ien.edu.sa).

### Quick start (placeholder — fill in after build)
```bash
# Install dependencies
pip install -r requirements.txt

# One-time corpus preparation: OCR, chunk, embed, build Chroma
python -m src.ingest.run --grades 4 7 10

# Launch the Chainlit UI
chainlit run src/ui/app.py
```

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
- [NAMAA-Space](https://huggingface.co/NAMAA-Space) for the Qari Arabic OCR model.
- [HUMAIN](https://huggingface.co/humain-ai) / [SDAIA](https://sdaia.gov.sa/) for ALLaM, the Saudi national LLM.
- [Jina AI](https://jina.ai/) for the embedding and reranker models.
- The Applied AI Bootcamp instructors and cohort.
