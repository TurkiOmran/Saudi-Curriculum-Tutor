# Aleem — Build Spec

Locked design decisions from the grilling session. Build to this; revisit only with cause.

---

## 1. Deliverable Shape

- **Primary deliverable:** Live demo (graded). Recording + slides produced afterwards.
- **Scope:** Demo-first; benchmark phase deferred until after the live demo.
- **Timeline:** 2 weeks, team of 2.

---

## 2. Architecture

```
User request + grade + subject (Chainlit ChatProfile selector)
  ↓
Conversation memory: rewrite the message into a standalone question
  using recent chat history ("quiz me on that" → "quiz me on photosynthesis")
  ↓
Query decomposition agent (split compound requests)
  ↓ for each sub-request:
    Intent classifier → one of {Q&A, explain, summarize, revise, quiz}
    ↓
    Embed query with Jina-v4 (retrieval.query mode)
    ↓
    Chroma top-20 from the user's grade collection (filtered by subject)
    ↓
    Jina Reranker v3 → top-5
    ↓
    ALLaM-7B self-check: "is the answer in these chunks? yes/no"
       ├─ no  → refusal + parent lesson titles of top-3 chunks
       └─ yes → ALLaM grounded generation with inline [n] citations
  ↓
Merge sub-answers → Chainlit renders with expandable source cards
```

---

## 3. Stack

| Layer | Choice | Notes |
| --- | --- | --- |
| OCR | `NAMAA-Space/Qari-OCR-0.4.0-VL-4B-Instruct` | Validate on 20-page sample before committing. Vision-LLM fallback (Gemini Flash) for hard pages if needed. |
| Embedding | `jinaai/jina-embeddings-v4` | Use `retrieval.query` vs `retrieval.passage` task modes. |
| Vector store | Chroma (persistent local) | One collection per grade: `grade_4`, `grade_7`, `grade_10`. |
| Reranker | Jina Reranker v3 | Single Jina ecosystem. Verify exact HF model ID at install time. |
| Generator | `humain-ai/ALLaM-7B-Instruct-preview` | Quantize to 4-bit if VRAM is tight. Also used for self-check and intent classifier. |
| UI | Chainlit | Native source elements, streaming, `ChatProfile` for grade+subject. Custom RTL Arabic CSS. |
| Orchestration | LangGraph | Pipeline has a per-task loop + a self-check branch + shared state — a graph shape, not a linear LCEL chain. Same ecosystem as the proposal's LangChain. |

---

## 4. Pipeline Details (Locked)

### 4.1 OCR
- Per-page text-vs-scan detection.
- Digital-text pages: extract with PyMuPDF / pdfplumber. No OCR.
- Scanned pages: route to Qari.
- Math pages have a go/no-go gate on day 3–4 based on equation transcription quality.
- Diagrams: skipped for this iteration. Jina-v4 multimodal embedding of cropped figures is documented as a post-demo stretch.

### 4.2 Chunking
- **Structure-aware** at lesson/section level.
- Each chunk metadata: `{grade, subject, book, chapter, lesson_title, page, content_type}`.
- `content_type ∈ {lesson_body, example, exercise, definition}` — tagged by an LLM post-pass if heading detection is unreliable.

### 4.3 Retrieval
- Dense-only with Jina-v4. **No BM25, no hybrid.**
- `top-20 retrieval → Jina Reranker v3 → top-5 → LLM`.
- Grade isolation is structural (separate collections per grade), not policy-based.
- Subject is a metadata filter at query time.

### 4.4 Generation
- Generator: ALLaM-7B-Instruct-preview.
- Grounding-strict system prompt requires:
  - Answer only from retrieved chunks.
  - Inline `[n]` citation markers per claim.
  - Exact refusal phrase if context is insufficient: `لم أجد هذا في الكتاب المدرسي` / `I couldn't find this in your textbook`.
  - Respond in the user's query language.
- Format retries on JSON/citation breakage **deferred** — implement only if §6.2 faithfulness eval shows real-world citation breakage (out-of-range `[n]`, missing citations, malformed brackets). Until then the pipeline trusts the model's output and parses it as-is.

### 4.5 Refusal Path
- **LLM self-check only** (no score threshold). ALLaM is asked "do these chunks contain the answer? yes/no" before generation.
- On refusal: return canonical phrase + the **parent lesson titles** of the top-3 retrieved chunks, framed as "Related topics in your textbook". No additional retrieval; reuse already-retrieved chunks.
- Instrument: log top-k scores + self-check verdict for every query so a threshold can be added later if data warrants.

### 4.6 Agentic Layer
- **Conversation memory (query rewrite).** Recent chat history is kept per session. Before decomposition, one cheap LLM call rewrites the incoming message into a self-contained question using that history (e.g., "quiz me on that" → "quiz me on photosynthesis"). Everything downstream always receives a standalone question, so no other node needs history awareness.
  - Implemented as a cuttable prefix node — if week 2 is tight, disable it and the pipeline still works on fully-specified questions.
  - "Session" therefore means app settings (grade/subject) **plus** recent chat turns.
- **Query decomposition agent** at the top of the pipeline. Splits compound requests (e.g., "explain X and quiz me") into atomic sub-requests. Each sub-request flows through the intent classifier + RAG independently; results merged in the final response.
  - Always runs as a node; output is always a list of tasks — `[query]` for a single-task request, `[task1, task2]` for a compound one. A config flag can force `[query]` without an LLM call (the cut-it escape hatch for Risk #4).
- **No retry/reformulation loop** in this iteration.

### 4.7 Intent Classifier
- Few-shot prompt mapping each request to one of: Q&A, explain, summarize, revise, quiz.
- Implemented as an ALLaM call (or a small fast model) with structured output.
- Each mode has its own generation prompt template; all share the same retrieval layer and grounding contract.
- `teacher-support` was previously listed and has been dropped: no defined behavior, no eval coverage, and any plausible interpretation either needs content sources outside the textbook chunks or breaks the grounding contract. Listed as post-demo roadmap.

### 4.8 UI
- Chainlit with:
  - `ChatProfile` for grade + subject selection at session start (state held in session/localStorage; no auth).
  - RTL Arabic layout — proper mirroring, not just `direction: rtl`. Arabic-friendly font (IBM Plex Sans Arabic / Cairo).
  - Streaming responses.
  - **Lesson-level citations**, inline numbered `[n]`, with expandable source cards showing the exact retrieved passage.

---

## 5. Scope

### 5.1 Grades
Grades **4, 7, 10** — one per stage (elementary / middle / high school).

### 5.2 Subjects
Five per grade: **Arabic, Islamic studies, social studies, English, Math**.
- Math is conditional on Qari OCR validation. If math-page equation transcription is unusable, drop math and fall back to 4 text-heavy subjects.

### 5.3 Out of Scope (for this demo)
- Diagram understanding (skipped; multimodal Jina-v4 is a stretch).
- Equation rendering beyond text-OCR (no LaTeX-typeset display).
- User authentication / profiles.
- Production multi-tenancy.

---

## 6. Evaluation

### 6.1 Demo-Phase Smoke Set
- **60 questions total.**
- 70% authored from end-of-chapter exercises with gold answer + source page.
- 20% **should-refuse** off-curriculum questions to validate refusal works.
- 10% adversarial bilingual (Arabic question about English textbook content and vice versa).
- One teammate authors, the other reviews.

### 6.2 Metrics for Demo Phase
- **Retrieval:** Recall@5 — did the gold source chunk appear in the top-5 reranked results?
- **Refusal:** Precision and recall on the should-refuse subset.
- **Faithfulness:** Manual eyeball on ~20 generated answers — do all claims trace to retrieved chunks?
- Full RAGAS metrics deferred to benchmark phase.

### 6.3 Benchmark Phase (Post-Demo)
- 150–300 question gold set, same format, published as a HuggingFace dataset.
- Embedding bake-off (Jina-v4 vs BGE-M3 vs Multilingual-E5 vs Arabic-Triplet-Matryoshka).
- ALLaM vs Claude/Gemini generator comparison.
- RAGAS faithfulness, answer correctness, context precision.

---

## 7. Compute & Deployment

- **OCR, chunking, embedding** all run offline, once. Outputs persisted to the repo (Chroma DB file checked in or attached release).
- **At query time** only Jina-v4 (query embedding), Jina Reranker v3, and ALLaM-7B run live.
- **Primary inference:** cloud GPU (Modal / Runpod / Lambda — to be finalized).
- **Chainlit UI:** local laptop during the demo.
- **Backup for demo day:** pre-tested cloud GPU instance with the full stack, in case the local/primary path fails.

---

## 8. Top Risks (Watch List)

1. **Qari quality on math pages.** Drives the math go/no-go decision on day 3–4. Validate early.
2. **ALLaM grounding discipline under thin context.** 7B models hallucinate confidently. Mitigated by strict prompt + self-check + format retries.
3. **Live demo robustness.** Network/GPU failure on demo day. Cloud GPU fallback is mandatory, not optional.
4. **Decomposition agent eating week 2.** Additive feature, not on the critical path. Cut without hesitation if base Q&A isn't solid by day 9.
5. **RTL Arabic UI polish in Chainlit.** Not first-class; budget time for CSS overrides.

---

## 9. Open Decisions (Not Yet Locked)

- Exact cloud GPU provider (Modal vs Runpod vs Lambda).
- Final Jina Reranker version (v2 multilingual vs v3 — verify availability).
- Quantization scheme for ALLaM if VRAM-bound (4-bit AWQ / GPTQ / bitsandbytes).
- Math content_type tagging strategy if equations survive OCR.

---

## 10. Task List

See `TaskList` in the agent harness — 22 tasks queued covering download → OCR → chunking → embedding → Chroma → retrieval/rerank → ALLaM → prompts → self-check → refusal → intent classifier → decomposition → Chainlit UI → citations → eval set → eval iteration → cloud fallback → demo script → dry runs.

---

*Spec frozen post-grilling. Changes require a new grill round.*
