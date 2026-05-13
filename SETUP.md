# Setup

How to get Aleem running on your machine from a fresh clone.

> **Current build status:** UI shell + empty Chroma collections.
> The retrieval, reranking, and generation layers are not wired in yet —
> see `BUILD_SPEC.md §10` for the task list. Once you've finished setup,
> the Chainlit UI will boot, capture your `(grade, subject)` selection,
> and reply with a placeholder confirming the captured state.

---

## 1. Prerequisites

| Requirement      | Version / Notes                                                            |
| ---------------- | -------------------------------------------------------------------------- |
| **Python**       | **3.11** exactly (pinned in `.python-version`). 3.12+ is *not* tested.     |
| **uv**           | Recommended package manager. Resolves + installs the full dep tree in seconds. |
| **git**          | Any recent version.                                                        |
| **HuggingFace**  | An account + access token. Required *later* (when ingestion runs Jina-v4); not needed to launch the shell. |
| **GPU**          | Optional. The shell runs fine on CPU. Embedding + generation phases (coming later) will benefit from a GPU. |
| **Disk**         | ~5 GB free — most of that is `torch` + model caches once you embed.        |

### Install uv

**macOS (Homebrew):**
```bash
brew install uv
```

**macOS / Linux (one-line installer):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:
```bash
uv --version
# uv 0.11.x or newer
```

> uv manages the Python interpreter for you — you do not need to install
> Python 3.11 separately. `uv sync` (next step) will download CPython 3.11
> automatically if it's missing, matching the version pinned in
> `.python-version`.

---

## 2. Clone the repo

```bash
git clone <repo-url> Aleem
cd Aleem
```

That's the whole step. `uv` handles the venv in the next step — you don't
need to create one manually.

---

## 3. Install dependencies

All deps are locked in `uv.lock` (committed) with exact versions and wheel
hashes. `uv sync` reads the lock file and installs into a project-local
`.venv/` directory, producing a byte-identical environment for everyone on
the team and for CI/Docker.

```bash
uv sync
```

First run takes a couple of minutes (torch is the heavy item) and creates
`.venv/` at the repo root. Subsequent runs are near-instant.

> **Why `transformers==4.57.6` and not 5.x?** Jina-v4's `trust_remote_code`
> model loader was written against the 4.x API and isn't yet verified on 5.x.
> See the comment block at the top of `pyproject.toml`.

### Pip fallback (no uv)

If you really cannot install uv (e.g. a locked-down CI image), there is a
pip-compatible `requirements.txt` checked in. It is **auto-generated from
`uv.lock`** — do not hand-edit it. Use:

```bash
python3.11 -m venv .venv
source .venv/bin/activate           # macOS / Linux
# .venv\Scripts\activate            # Windows
pip install --upgrade pip
pip install -r requirements.txt
```

This installs the same closure but without lock-file hash verification
and at roughly pip's normal speed. To regenerate `requirements.txt` after
a dep bump:

```bash
uv export --format requirements-txt --no-hashes --no-emit-project \
  --output-file requirements.txt
```

---

## 4. Configure environment variables

Copy the template and fill it in:

```bash
cp .env.example .env
```

Open `.env` and set:

| Var          | Required?            | What it does                                                              |
| ------------ | -------------------- | ------------------------------------------------------------------------- |
| `HF_TOKEN`   | Only for ingestion   | Used by `transformers` to download `jinaai/jina-embeddings-v4` (a gated model — accept the license on its HF page first). Get a token at <https://huggingface.co/settings/tokens>. |
| `CHROMA_DIR` | No (defaults to `./chroma`) | Override where Chroma persists its SQLite + parquet files.        |

For now (UI shell only), you can leave `HF_TOKEN` blank — the shell never
loads Jina-v4. You'll need it when ingestion is wired up.

---

## 5. Initialise the Chroma collections

This creates three empty persistent collections — one per grade — with the
Jina-v4 embedding function pre-attached.

```bash
uv run python -m src.retrieval.init_chroma
```

> `uv run` runs a command inside the project's `.venv` without you having
> to `source .venv/bin/activate` first. If you prefer the traditional
> flow, activate the venv and drop the `uv run` prefix.

Expected output:
```
HH:MM:SS  INFO     chroma dir: /…/Aleem/chroma
HH:MM:SS  INFO     grade_4    created  (count=0)
HH:MM:SS  INFO     grade_7    created  (count=0)
HH:MM:SS  INFO     grade_10   created  (count=0)
HH:MM:SS  INFO     done — 3 collections ready
```

Re-running is safe (idempotent) — existing collections are reported as
`exists` instead of `created`.

Confirm the persisted database:
```bash
ls chroma/
# README.md  chroma.sqlite3  <uuid-dirs>/
```

---

## 6. Run the Chainlit UI

Chainlit reads its config (`.chainlit/config.toml`), welcome screen
(`chainlit.md`), and static assets (`public/`) from the current working
directory, so we run it from inside `src/ui/`. `PYTHONPATH=../..` keeps
imports of `src.retrieval...` resolvable when the pipeline lands.

```bash
cd src/ui
PYTHONPATH=../.. uv run chainlit run app.py
```

Open <http://localhost:8000> in your browser. You should see three grade
cards: **Grade 4 / Grade 7 / Grade 10**.

### What works today

1. Pick a grade → opens a chat scoped to that grade.
2. Click the settings gear (⚙) → pick a subject from the dropdown.
3. Send any message → reply confirms the captured `(grade, subject)` state.

### What's stubbed

`@cl.on_message` returns a placeholder. Once `src/ingest/`, real
retrieval, Jina Reranker v3, and ALLaM-7B are wired in, the same handler
will route through the full pipeline — the `(grade, subject)` captured
here already feed into the future Chroma query (see `src/ui/README.md`).

---

## 7. Useful commands cheat-sheet

```bash
# install / sync deps from the lock file
uv sync

# add a new dependency (updates pyproject.toml + uv.lock)
uv add <package>

# regenerate requirements.txt from uv.lock (for pip fallback)
uv export --format requirements-txt --no-hashes --no-emit-project \
  --output-file requirements.txt

# (re)initialise Chroma — idempotent
uv run python -m src.retrieval.init_chroma

# inspect the persisted collections from the CLI
uv run python -c "from src.retrieval.chroma_client import get_collection; \
                  print({n: get_collection(n).count() for n in (4, 7, 10)})"

# launch the UI
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py)

# launch on a custom port
(cd src/ui && PYTHONPATH=../.. uv run chainlit run app.py --port 8765)
```

---

## 8. Troubleshooting

**`chainlit: command not found`**
You forgot the `uv run` prefix, or you didn't activate the venv. Either
run `uv run chainlit run app.py` or do `source .venv/bin/activate` first.

**`ModuleNotFoundError: No module named 'src'`**
You forgot `PYTHONPATH=../..` when running Chainlit from `src/ui/`, or
you're not at the repo root when running `uv run python -m src.retrieval.init_chroma`.

**`uv: command not found`**
uv isn't on your PATH. Re-run the installer (see §1) or restart your
shell. The Homebrew install puts it in `/opt/homebrew/bin/`; the
one-line installer puts it in `~/.local/bin/`.

**Chainlit creates a stray `chainlit.md` at the repo root**
You launched Chainlit from the repo root instead of from `src/ui/`.
Stop the server (`Ctrl-C`), delete the auto-generated `chainlit.md`
and `.chainlit/` at the repo root, then `cd src/ui` before launching.

**Chroma errors mentioning a missing embedding function on `get_collection`**
The embedding function must be supplied every time you open a
collection — that's what `src/retrieval/chroma_client.get_collection()`
does for you. Don't call `client.get_collection(...)` directly; use the
helper.

**`pip install` fails on `torch`**
On Apple Silicon, `torch==2.7.1` should resolve to a universal wheel. On
older Linux, you may need to add `--extra-index-url https://download.pytorch.org/whl/cpu`
to force the CPU build.

**HuggingFace 401 / 403 when downloading Jina-v4** *(later, when ingestion runs)*
You haven't accepted the model license. Visit
<https://huggingface.co/jinaai/jina-embeddings-v4>, click *Agree*, and
make sure `HF_TOKEN` in your `.env` belongs to the same account.

---

## 9. Where to go next

| If you want to…                       | Open                                       |
| ------------------------------------- | ------------------------------------------ |
| Understand the design                 | `BUILD_SPEC.md`                            |
| Understand the project pitch          | `README.md`                                |
| Work inside the retrieval layer       | `src/retrieval/README.md`                  |
| Work on the Chainlit UI               | `src/ui/README.md`                         |
| See what's in the Chroma folder       | `chroma/README.md`                         |
| Check off remaining build tasks       | `BUILD_SPEC.md §10`                        |
