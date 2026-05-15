"""L18 logging — `@timed` decorator + `log_query` JSONL writer."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.graph.logging import log_query, timed


async def test_timed_adds_latency_ms_key():
    @timed("dummy")
    async def node(state):
        return {"answer": "x"}

    out = await node({})
    assert "latency_ms" in out["debug"]
    assert "dummy" in out["debug"]["latency_ms"]
    assert out["debug"]["latency_ms"]["dummy"] >= 0
    assert out["answer"] == "x"


async def test_timed_merges_with_existing_debug():
    @timed("alpha")
    async def node(state):
        return {"debug": {"upstream_key": 42, "latency_ms": {"earlier": 5}}}

    out = await node({"debug": {"older_key": "preserved"}})
    # Existing keys preserved
    assert out["debug"]["older_key"] == "preserved"
    assert out["debug"]["upstream_key"] == 42
    # Latency map merged, not overwritten
    assert out["debug"]["latency_ms"]["earlier"] == 5
    assert out["debug"]["latency_ms"]["alpha"] >= 0


def test_log_query_writes_jsonl_line(tmp_path, monkeypatch):
    # Redirect the logs dir into a temp location
    monkeypatch.setattr("src.graph.logging.LOGS_DIR", tmp_path)

    outer_state = {
        "user_query": "what is photosynthesis?",
        "standalone_question": "what is photosynthesis?",
        "grade": 7,
        "subject": "islamic_studies",
        "language": "en",
        "debug": {"latency_ms": {"rewrite": 10, "decompose": 5}},
        "tasks": [
            {
                "intent": "qa",
                "self_check_passed": True,
                "refused": False,
                "debug": {
                    "rerank_scores": [0.9, 0.8],
                    "self_check_verdict": "yes",
                    "citations_count": 2,
                    "latency_ms": {"intent": 100, "generate": 500},
                },
            }
        ],
    }
    log_query(outer_state)

    log_file = tmp_path / f"queries-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])

    # L18 record-shape contract
    for field in (
        "ts",
        "session_id",
        "query",
        "grade",
        "subject",
        "language",
        "intent",
        "rerank_scores",
        "self_check_passed",
        "refused",
        "num_tasks",
        "citations_count",
        "latency_ms",
    ):
        assert field in rec, f"missing field {field!r}"

    assert rec["intent"] == "qa"
    assert rec["self_check_passed"] is True
    # Latencies from outer + inner flatten into one dict
    assert rec["latency_ms"]["rewrite"] == 10
    assert rec["latency_ms"]["intent"] == 100


def test_log_query_swallows_failure_does_not_raise(monkeypatch, tmp_path):
    """log_query failure must never break the pipeline."""
    monkeypatch.setattr("src.graph.logging.LOGS_DIR", tmp_path / "nonexistent")
    # Even with weird input, log_query should not propagate
    try:
        log_query({"tasks": [], "debug": {}})
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"log_query raised: {exc}")
