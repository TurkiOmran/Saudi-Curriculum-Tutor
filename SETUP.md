# Setup

How to get Aleem running on your machine from a fresh clone.

> **Current build status:** The full agentic pipeline is **built and
> tested** — rewrite → decompose → intent → retrieve → self-check →
> (generate | refuse | chat) → citations → merge, all wired through
> Chainlit with per-node streaming and JSONL query logging.
> The only stub left is `retrieve()` — it returns 3 hardcoded
> photosynthesis chunks (per L2) until the ingestion half lands. So
> with `backend: fake` the whole graph runs end-to-end with **no API
> key**; with `backend: openrouter` you get real Llama-3.3-70B answers
> grounded in those 3 stub chunks.

---

## 1. Prerequisites

| Requirement      | Version / Notes                                                            |
| ---------------- | -------------------------------------------------------------------------- |
| **Python**       | **3.11** exactly (pinned in `.python-version`). 3.12+ is *not* tested.     |
| **uv**           | Recommended package manager. Resolves + installs the full dep tree in seconds. |
| **git**          | Any recent version.                                                        |
| **OpenRouter**   | Optional. Needed only for real LLM answers — see §5. `backend: fake` works without it. |
| **HuggingFace**  | Optional. Needed only when the (collaborator-owned) ingestion pipeline runs Jina-v4. The agentic pipeline never touches HF. |
| **GPU**          | Optional. Everything in this branch runs on CPU. ALLaM-7B local deployment will benefit from a GPU; OpenRouter offloads that. |
| **Disk**         | ~5 GB free — torch + model caches dominate once HF downloads land.         |

### Install uv

```bash
# macOS (Homebrew)
brew install uv

# macOS / Linux (one-line installer)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Verify
uv --version       # uv 0.11.x or newer
```

> uv manages the Python interpreter for you — you do **not** need to
> install Python 3.11 separately. `uv sync` (§3) downloads CPython 3.11
> if it's missing, matching `.python-version`.

---

## 2. Clone the repo

```bash
git clone <repo-url> Aleem
cd Aleem
```

That's the whole step. `uv` handles the venv in §3.

---

## 3. Install dependencies

All deps are locked in `uv.lock` (committed) with exact versions and wheel
hashes. `uv sync` installs into a project-local `.venv/`, producing a
byte-identical environment for everyone on the team and CI.

```bash
uv sync                     # runtime + dev deps (pytest, ruff)
```

First run takes ~2 min (torch is the heavy item). Subsequent runs are
near-instant.

### Pip fallback (no uv)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is auto-generated from `uv.lock` — do not hand-edit.
To regenerate after a dep bump:

```bash
uv export --format requirements-txt --no-hashes --no-emit-project \
  --output-file requirements.txt
```

---

## 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set whichever keys you need. All are optional for the
default `backend: fake` flow:

| Var                  | When required                              | What it does                                                          |
| -------------------- | ------------------------------------------ | --------------------------------------------------------------------- |
| `OPENROUTER_API_KEY` | Only when `llm.backend: openrouter`        | Real LLM calls. Get a key at <https://openrouter.ai/keys>.            |
| `HF_TOKEN`           | Only for (future) ingestion via Jina-v4    | The model is gated — accept the license on its HF page first.         |
| `CHROMA_DIR`         | No (defaults to `./chroma`)                | Override where Chroma persists its SQLite + parquet files.            |

---

## 5. Choose your LLM backend (`config.yaml`)

`config.yaml` lives at the repo root. The shape is locked in
`RESPONSE_WORKFLOW.md` L17.

```yaml
llm:
  backend: fake          # fake | openrouter | ollama (one at a time)

  openrouter:
    model: meta-llama/llama-3.3-70b-instruct
    base_url: https://openrouter.ai/api/v1
    # api key read from OPENROUTER_API_KEY in .env
```

### `backend: fake`  *(default, no API key needed)*

Every LLM node short-circuits to a canned reply. The graph still runs
end-to-end — you'll see the streaming `cl.Step` cascade, citations, the
JSONL log line, etc. Great for UI work, demos, and the test suite.

### `backend: openrouter` *(real LLM)*

1. Add `OPENROUTER_API_KEY=…` to `.env`.
2. Flip `backend: openrouter` in `config.yaml`.
3. About the model:
   - `meta-llama/llama-3.3-70b-instruct` (no `:free`) → paid route,
     ~$0.001/query. Reliable, doesn't 429. **Recommended.**
   - `meta-llama/llama-3.3-70b-instruct:free` → free route via 3rd-party
     upstream provider; heavily rate-limited. Expect HTTP 429 retries on
     bursty pipelines like Aleem (5 LLM calls per query).
   - Smaller free models (`nvidia/nemotron-nano-9b-v2:free`,
     `openai/gpt-oss-20b:free`) are less throttled but weaker at
     structured output.
4. The model **must** support tool-calling (L13). Verify against the live
   list at <https://openrouter.ai/api/v1/models> — the free roster rotates.

### `backend: ollama`

Placeholder slot in `config.yaml`. The factory raises `NotImplementedError`
until a local target is decided.

---

## 6. Initialise the Chroma collections

The agentic pipeline doesn't read from Chroma yet (retrieve is stubbed),
but the collections need to exist so the rest of the stack imports cleanly.

```bash
uv run python -m src.retrieval.init_chroma
```

Expected output:
```
HH:MM:SS  INFO  chroma dir: /…/Aleem/chroma
HH:MM:SS  INFO  grade_4   created  (count=0)
HH:MM:SS  INFO  grade_7   created  (count=0)
HH:MM:SS  INFO  grade_10  created  (count=0)
HH:MM:SS  INFO  done — 3 collections ready
```

Idempotent — safe to re-run.

---

## 7. Verify the install

Two fast checks, no browser needed:

```bash
# (a) Run the pipeline end-to-end with the fake backend — no network.
uv run python scripts/smoke_run.py "what is photosynthesis?"

# (b) Run the test suite (~1.5s, 61 tests, all fake-backend).
uv run pytest

# (c) Lint check.
uv run ruff check src/ tests/ scripts/
```

Both `pytest` and `ruff check` should report green. The smoke run prints
the canned stub answer plus the per-task debug dict. With `backend:
openrouter` the smoke run prints a real grounded answer.

---

## 8. Run the Chainlit UI

```bash
cd src/ui
PYTHONPATH=../.. uv run chainlit run app.py
```

Open <http://localhost:8000>. Pick a grade card, then optionally change
subject in the ⚙ settings panel, then ask any question.

### What you see per query

- A single status line at the top of the answer (e.g. `⏳ Detecting
  intent…`) that **updates in place** as each node runs and **disappears**
  once the final answer renders (ChatGPT / Claude.ai pattern, per L21).
- Real answers stream token-by-token from the generate / chat nodes.
- Citation cards (`[1]`, `[2]`, …) expand to show the source chunk's
  text, lesson title, and page.
- Off-textbook questions hit the L1 refusal path:
  `I couldn't find this in your textbook` / `لم أجد هذا في الكتاب المدرسي`
  plus the top-3 related lesson titles.
- Greetings / small talk / meta-questions hit the L22 chat path: friendly
  bounded reply, no citations, no factual content.

### What you don't see

Per-node `cl.Step` cards are deliberately gone (replaced by the single
updating status line per L21 iteration). The full per-node trace lives
in `logs/queries-$(date +%F).jsonl` — tail it in a separate terminal:

```bash
tail -f logs/queries-$(date +%F).jsonl
```

---

## 9. Useful commands cheat-sheet

```bash
# Install / sync deps
uv sync

# Add a dep (updates pyproject.toml + uv.lock)
uv add <package>

# Regenerate requirements.txt
uv export --format requirements-txt --no-hashes --no-emit-project \
  --output-file requirements.txt

# (Re)initialise Chroma
uv run python -m src.retrieval.init_chroma

# Smoke-run the pipeline (no UI)
uv run python scripts/smoke_run.py "your question here"

# Tests
uv run pytest                                        # full suite
uv run pytest tests/test_intent.py                   # one file
uv run pytest -vv -s                                 # verbose

# Lint / format
uv run ruff check src/ tests/ scripts/
uv run ruff check --fix src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/

# Launch the Chainlit UI
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py)
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py --port 8765)

# Tail today's query log
tail -f logs/queries-$(date +%F).jsonl
```

---

## 10. Troubleshooting

**`chainlit: command not found`**
Forgot `uv run`, or didn't activate the venv. Either run
`uv run chainlit run app.py` or do `source .venv/bin/activate` first.

**`ModuleNotFoundError: No module named 'src'`**
Forgot `PYTHONPATH=../..` when running Chainlit from `src/ui/`, or you're
not at the repo root when running `uv run python -m src.retrieval.init_chroma`.

**`uv: command not found`**
uv isn't on PATH. Re-run the installer (§1) or restart your shell.

**Chainlit drops a stray `chainlit.md` or `.chainlit/` at the repo root**
You launched Chainlit from the repo root instead of from `src/ui/`. Stop
the server, delete the stray files at root, then `cd src/ui` before
launching. `.gitignore` already excludes the repo-root `.chainlit/`.

**HTTP 429 / "rate-limited upstream" from OpenRouter**
You're on a `:free` model and the third-party upstream provider is
throttling. Two fixes:
- Switch to the paid route (drop `:free` from the model id; costs
  ~$0.001/query and stops the throttling). Requires credits on your
  OpenRouter account — `is_free_tier: false` on `/api/v1/auth/key`.
- Switch to a smaller / less-popular free model
  (`nvidia/nemotron-nano-9b-v2:free`, `openai/gpt-oss-20b:free`).

**HTTP 404 / "No endpoints found for `<model>:free`"**
That free endpoint was retired. Refresh the model id against
<https://openrouter.ai/api/v1/models> and pick a currently-live one.

**`Structured Output response does not have a 'parsed' field`** *(pipeline error in Chainlit)*
A provider hiccup — the LLM returned an empty `tool_calls=[]` instead of
a parsed schema. The pipeline now catches this per L20 and falls back
to safe defaults (intent → qa or chat-heuristic; self_check → refuse).
If you still see the error card, re-launch Chainlit so the latest code
is loaded.

**Chroma "missing embedding function on `get_collection`"**
Don't call `client.get_collection(...)` directly. Use
`src.retrieval.chroma_client.get_collection(grade)` — it re-attaches Jina-v4
each open, which Chroma can't persist.

**`pip install` fails on `torch`**
On Apple Silicon, `torch==2.7.1` resolves to a universal wheel. On older
Linux, add `--extra-index-url https://download.pytorch.org/whl/cpu` to
force the CPU build.

**HuggingFace 401 / 403 when downloading Jina-v4** *(later, when ingestion runs)*
You haven't accepted the model license. Visit
<https://huggingface.co/jinaai/jina-embeddings-v4>, click **Agree**, and
make sure `HF_TOKEN` in your `.env` matches that account.

---

## 11. Where to go next

| If you want to…                       | Open                                       |
| ------------------------------------- | ------------------------------------------ |
| Understand the project pitch          | `README.md`                                |
| Understand the locked design          | `BUILD_SPEC.md` (§1–§10)                   |
| Understand the agentic-layer decisions | `RESPONSE_WORKFLOW.md` (L1–L22)           |
| Navigate the codebase (for Claude)    | `CLAUDE.md`                                |
| Work inside the retrieval layer       | `src/retrieval/README.md`                  |
| Work inside the agentic graph         | `src/graph/README.md`                      |
| Work inside the Chainlit UI           | `src/ui/README.md`                         |
| Add or read tests                     | `tests/README.md`                          |
| Edit a prompt                         | `prompts/README.md` + `prompts/*.j2`       |
| See what's in `chroma/`               | `chroma/README.md`                         |
