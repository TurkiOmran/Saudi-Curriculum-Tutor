"""Outer graph integration. Rewrite → decompose → map_tasks → merge + L18 log."""

from __future__ import annotations

import json
from datetime import datetime

from src.graph.outer import outer_graph


async def test_full_pipeline_single_task(make_outer_state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.graph.logging.LOGS_DIR", tmp_path)
    state = make_outer_state(user_query="What is photosynthesis?")
    result = await outer_graph.ainvoke(state)

    assert result["final_answer"]
    assert len(result["tasks"]) == 1
    task = result["tasks"][0]
    assert task["intent"] == "qa"
    assert task["self_check_passed"] is True
    assert task["refused"] is False
    assert len(task["citations"]) >= 1


async def test_pipeline_writes_jsonl_record(make_outer_state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.graph.logging.LOGS_DIR", tmp_path)
    state = make_outer_state(user_query="What is photosynthesis?")
    await outer_graph.ainvoke(state)

    log_file = tmp_path / f"queries-{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    assert log_file.exists()
    rec = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert rec["query"] == "What is photosynthesis?"
    assert rec["grade"] == 7
    assert rec["intent"] == "qa"
    # Per-node latencies present (both outer + inner)
    assert "rewrite" in rec["latency_ms"]
    assert "intent" in rec["latency_ms"]
    assert "generate" in rec["latency_ms"]


async def test_arabic_query_detected(make_outer_state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.graph.logging.LOGS_DIR", tmp_path)
    state = make_outer_state(user_query="ما هو التمثيل الضوئي؟")
    result = await outer_graph.ainvoke(state)
    # L16 regex fallback (since fake backend skips the rewrite LLM call)
    assert result["language"] == "ar"


async def test_history_in_outer_propagates_to_tasks(make_outer_state, tmp_path, monkeypatch):
    monkeypatch.setattr("src.graph.logging.LOGS_DIR", tmp_path)
    state = make_outer_state(
        user_query="hello",
        history=[{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "reply"}],
    )
    result = await outer_graph.ainvoke(state)
    # decompose creates task(s); each carries the history through
    assert result["tasks"][0]["history"][0]["content"] == "earlier"
