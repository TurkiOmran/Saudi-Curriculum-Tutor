# `chroma/` — persistent vector store

ChromaDB persists its SQLite + parquet files here. **The DB files are
gitignored; only this README is tracked.**

## What lives here (after running setup)

```
chroma/
├── README.md              ← tracked
├── chroma.sqlite3         ← gitignored (Chroma's metadata DB)
└── <uuid>/                ← gitignored (per-collection HNSW indexes + parquet)
```

The directory will be empty after a fresh clone. Run the setup script to
populate it.

## How to recreate from scratch

```bash
# from repo root
uv run python -m src.retrieval.init_chroma
```

This creates three collections — `grade_4`, `grade_7`, `grade_10` — each
with the Jina-v4 embedding function attached. The collections start empty;
the ingestion pipeline (forthcoming) will populate them.

`init_chroma.py` is idempotent: re-running it on an existing store is safe
and leaves the data untouched.

## Why one collection per grade

Grade isolation is **structural**, not policy-based. A Grade 4 student
literally cannot retrieve Grade 10 content because that data is in a
different collection. Subject is then a metadata filter *within* the
grade's collection. See `BUILD_SPEC.md §4.3`.

## Metadata schema (per chunk)

Every chunk added later will carry:

| Field          | Type | Example                          |
| -------------- | ---- | -------------------------------- |
| `grade`        | int  | `7`                              |
| `subject`      | str  | `"arabic"`                       |
| `book`         | str  | `"grade7_arabic_v2024.pdf"`      |
| `chapter`      | str  | `"الوحدة الثالثة"`               |
| `lesson_title` | str  | `"قواعد المد"`                   |
| `page`         | int  | `42`                             |
| `content_type` | str  | one of: `lesson_body`, `example`, `exercise`, `definition` |

See `BUILD_SPEC.md §4.2`.

## Not here (yet)

- Ingestion code — lives in `src/ingest/` once built.
- Anything that *reads* from these collections — lives in `src/retrieval/`.
