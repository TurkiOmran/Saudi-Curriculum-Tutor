"""L18 query logging — JSONL file + one-line stdout summary.

Two pieces:

- `@timed("node_name")` — a tiny decorator each graph node wears. It runs
  the wrapped node, records elapsed ms into `state.debug.latency_ms`, and
  returns the merged partial update. Without this decorator, per-node
  latency would have to be inferred externally from `astream_events`
  timestamps — fine for the UI but useless to the smoke script and
  future eval harness.

- `log_query(outer_state)` — called from the `merge` node so every query
  produces exactly one structured JSONL line and one short stdout
  summary, regardless of caller (Chainlit, smoke script, future API).

Stdout summary format per L18:
    [18:31:02] grade=7 ar intent=explain top1=0.94 ✓check 1240ms

JSONL fields:
    ts, session_id, query, standalone_question, grade, subject, language,
    intent, rerank_scores, self_check_passed, self_check_verdict, refused,
    num_tasks, citations_count, latency_ms.

`logs/` is gitignored; daily file rotation keeps the demo-day file easy
to identify.
"""

from __future__ import annotations

import functools
import json
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from src.config import REPO_ROOT
from src.graph.state import OuterState

LOGS_DIR = REPO_ROOT / "logs"

NodeFn = Callable[[Any], Awaitable[dict | None]]


def timed(node_name: str) -> Callable[[NodeFn], NodeFn]:
    """Wrap an async node so its latency lands in `state.debug.latency_ms`.

    Merges the node's own debug updates with the upstream debug dict so
    LangGraph's per-key overwrite semantics don't drop sibling fields
    (e.g. `rerank_scores` set upstream).
    """

    def decorator(fn: NodeFn) -> NodeFn:
        @functools.wraps(fn)
        async def wrapped(state):
            t0 = time.perf_counter()
            update = await fn(state) or {}
            latency = int((time.perf_counter() - t0) * 1000)

            existing = dict(state.get("debug") or {})
            from_update = dict(update.get("debug") or {})
            merged: dict[str, Any] = {**existing, **from_update}

            latency_ms = dict(merged.get("latency_ms") or {})
            latency_ms[node_name] = latency
            merged["latency_ms"] = latency_ms

            new_update = dict(update)
            new_update["debug"] = merged
            return new_update

        return wrapped

    return decorator


def _record(outer_state: OuterState) -> dict[str, Any]:
    tasks = outer_state.get("tasks") or []
    first = tasks[0] if tasks else {}
    outer_dbg = outer_state.get("debug") or {}
    task_dbg = first.get("debug") or {}

    # Flatten outer + inner latencies — outer keys first, inner overrides only
    # if names collide (they don't in our graph).
    latency_ms: dict[str, int] = {
        **(outer_dbg.get("latency_ms") or {}),
        **(task_dbg.get("latency_ms") or {}),
    }

    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "session_id": uuid.uuid4().hex[:12],
        "query": outer_state.get("user_query"),
        "standalone_question": outer_state.get("standalone_question"),
        "grade": outer_state.get("grade"),
        "subject": outer_state.get("subject"),
        "language": outer_state.get("language"),
        "intent": first.get("intent"),
        "rerank_scores": task_dbg.get("rerank_scores"),
        "self_check_passed": first.get("self_check_passed"),
        "self_check_verdict": task_dbg.get("self_check_verdict"),
        "refused": first.get("refused"),
        "num_tasks": len(tasks),
        "citations_count": task_dbg.get("citations_count"),
        "latency_ms": latency_ms,
    }


def _stdout_summary(rec: dict[str, Any]) -> str:
    ts = datetime.now().strftime("%H:%M:%S")
    grade = rec.get("grade") if rec.get("grade") is not None else "?"
    lang = rec.get("language") or "?"
    intent = rec.get("intent") or "?"
    scores = rec.get("rerank_scores") or []
    top1 = f"{scores[0]:.2f}" if scores else "—"

    if rec.get("refused"):
        check = "✗check"
    elif rec.get("self_check_passed") is True:
        check = "✓check"
    elif rec.get("self_check_passed") is False:
        check = "✗check"
    else:
        check = "-check"

    total_ms = sum((rec.get("latency_ms") or {}).values())
    return (
        f"[{ts}] grade={grade} {lang} intent={intent} top1={top1} "
        f"{check} {total_ms}ms"
    )


def log_query(outer_state: OuterState) -> None:
    """Write one JSONL line + print a one-line stdout summary."""
    rec = _record(outer_state)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"queries-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(_stdout_summary(rec), file=sys.stderr)
