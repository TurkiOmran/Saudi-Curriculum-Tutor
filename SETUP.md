# Setup

How to get Aleem running on your machine from a fresh clone.

> **Current build status:** The query path is **one tool-calling agent +
> topical verifier** per `docs/WORKFLOW_SANDBOX.md`.
> `src/graph/agent.py::run_agent` drives a `create_react_agent` whose
> only tool is `retrieve(query)`; the agent writes inline `[n]`
> citations, a parser flags structural issues, and a small
> structured-output LLM call checks topical relevance.
> The only stub left is `retrieve()`'s fallback — it returns 3 hardcoded
> photosynthesis chunks when the per-grade Chroma collection is empty
> (the test default). So with `backend: fake` (the shipped default) the
> whole agent runs end-to-end with **no API key** (canned reply, no tool
> calls); with `backend: openrouter` you get real tool-calling generation
> grounded in those 3 stub chunks until ingestion populates Chroma.
>
> `RESPONSE_WORKFLOW.md` (L1–L22) is preserved as the historical
> comparison baseline (`docs/WORKFLOW_SANDBOX.md` §12).

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

| Var                    | When required                                                  | What it does                                                          |
| ---------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------- |
| `OPENROUTER_API_KEY`   | Only when `llm.backend: openrouter`                            | Real LLM calls. Get a key at <https://openrouter.ai/keys>.            |
| `HF_TOKEN`             | Embeddings / reranker model download (gated Jina-v4)           | Accept the license on the HF model page first.                        |
| `MISTRAL_API_KEY`      | Only when running the ingest pipeline (`python -m src.ingest`) | Powers the Mistral OCR call. Key at <https://console.mistral.ai/api-keys/>. |
| `CHROMA_DIR`           | No (defaults to `./chroma`)                                    | Override where Chroma persists its SQLite + parquet files.            |
| `CHAINLIT_AUTH_SECRET` | Always (the UI registers an auth callback)                     | Signs the session cookie. Generate one with `uv run chainlit create-secret` and paste into `.env`. |

---

## 5. Choose your LLM backend (`config.yaml`)

`config.yaml` lives at the repo root. The base shape is locked in
`RESPONSE_WORKFLOW.md` L17; the `agent:` and `verifier:` blocks are
locked in `docs/WORKFLOW_SANDBOX.md` §8.

```yaml
llm:
  backend: fake          # fake | openrouter | ollama (one at a time)

  openrouter:
    model: meta-llama/llama-3.3-70b-instruct
    base_url: https://openrouter.ai/api/v1
    # api key read from OPENROUTER_API_KEY in .env

agent:
  max_tool_calls: 4      # §3 ceiling on retrieve() calls per turn

verifier:
  enabled: true          # §4 — default-on topical-relevance check
  model: ""              # empty → reuse llm.openrouter.model
                         # set to a smaller / faster model id when available
```

### `backend: fake`  *(default, no API key needed)*

`get_llm(for_agent=True)` returns a tool-aware `FakeListChatModel`
subclass whose canned reply has no tool calls — the agent loop
terminates after one LLM call, producing a stub answer with zero
retrieves. The verifier also short-circuits to `on_topic=True`. Great
for UI work, demos, and the test suite. Test code that wants to
exercise the full tool-call loop queues its own `AIMessage(tool_calls=…)`
via `FakeMessagesListChatModel` — see `tests/test_agent.py`.

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
4. The model **must** support tool-calling (the agent binds the `retrieve`
   tool via `bind_tools`). Verify against the live list at
   <https://openrouter.ai/api/v1/models> — the free roster rotates.

### `backend: ollama`

Placeholder slot in `config.yaml`. The factory raises `NotImplementedError`
until a local target is decided.

---

## 6. Initialise the Chroma collections

The collections need to exist so retrieve has a real backend to query
(it falls back to stub chunks if the per-grade collection is empty,
which is what the test suite relies on).

```bash
uv run python -m src.retrieval.init_chroma
```

Expected output:
```
HH:MM:SS  INFO  chroma dir: /…/Aleem/chroma
HH:MM:SS  INFO  grade_4   created  (count=0)
HH:MM:SS  INFO  grade_7   created  (count=0)
HH:MM:SS  INFO  grade_8   created  (count=0)
HH:MM:SS  INFO  grade_10  created  (count=0)
HH:MM:SS  INFO  done — 4 collections ready
```

Idempotent — safe to re-run.

---

## 7. Verify the install

Three fast checks, no browser needed:

```bash
# (a) Run the agent end-to-end with the fake backend — no network.
uv run python scripts/smoke_run.py "what is photosynthesis?"

# (b) Run the test suite (~4s, 65 tests, all fake-backend).
uv run pytest

# (c) Lint check.
uv run ruff check src/ tests/ scripts/
```

Both `pytest` and `ruff check` should report green. The smoke run prints
the canned stub answer, the (empty) tool-call list, the verifier verdict,
and the latency dict. With `backend: openrouter` the smoke run drives the
real agent, prints the verbatim search queries it made, and reports the
verifier's verdict on the grounded answer.

---

## 8. Run the Chainlit UI

```bash
cd src/ui
PYTHONPATH=../.. uv run chainlit run app.py
```

Open <http://localhost:8000>. Pick a grade card, then optionally change
subject in the ⚙ settings panel, then ask any question.

### What you see per query

- A single status line at the top of the answer that **updates in place**
  as the agent runs: starts at `⏳ Thinking…`, then becomes
  `🔎 Searching: "<verbatim query>"` for each retrieve call, and
  **disappears** once the final answer renders (ChatGPT / Claude.ai
  pattern).
- Real answers stream token-by-token from the agent's chat-model node.
- Citation cards (`[1]`, `[2]`, …) expand to show the source chunk's
  text, lesson title, and page.
- Off-topic answers and ceiling-hit refusals replace the streamed text
  with a warm, tutor-voiced refusal that suggests related topics drawn
  from whatever chunks were retrieved (docs/WORKFLOW_SANDBOX.md §3).
- Greetings / small talk: the agent simply doesn't call retrieve and
  produces a short conversational reply.

### What you don't see

The full per-turn trace — tool calls, citation flags, verifier verdict,
latency breakdown — lives in `logs/queries-$(date +%F).jsonl`. Tail it
in a separate terminal:

```bash
tail -f logs/queries-$(date +%F).jsonl
```

### Persistent chat history

Past chats appear in the left sidebar and survive browser refresh. State
lives in `./.aleem/chats.db` (SQLite, gitignored). The schema is applied
on first launch by `src/ui/persistence.py`. To wipe local history:

```bash
rm -rf .aleem/
```

The current build uses a single hardcoded local user (`identifier =
"local"`) so the data layer has someone to scope threads to — there's
no login screen. Real auth is deferred to deploy.

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
uv run pytest tests/test_agent.py                    # one file
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

**`Structured Output response does not have a 'parsed' field`** *(verifier path)*
A provider hiccup — the LLM returned an empty structured-output payload.
The verifier catches this in `src/graph/verifier.py` and falls back to
`on_topic=True` with the error type in the `reason` field, so the answer
still ships. If logs show this happening often, set `verifier.model` to a
more reliable model id in `config.yaml`.

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
| Understand the historical agentic-layer decisions | `RESPONSE_WORKFLOW.md` (L1–L22) |
| Understand the current agent shape    | `docs/WORKFLOW_SANDBOX.md`                 |
| Navigate the codebase (for Claude)    | `CLAUDE.md`                                |
| Work inside the retrieval layer       | `src/retrieval/README.md`                  |
| Work inside the agentic graph         | `src/graph/README.md`                      |
| Work inside the Chainlit UI           | `src/ui/README.md`                         |
| Add or read tests                     | `tests/README.md`                          |
| Edit a prompt                         | `prompts/README.md` + `prompts/*.j2`       |
| See what's in `chroma/`               | `chroma/README.md`                         |
