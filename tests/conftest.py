"""Shared pytest fixtures.

Force `backend=fake` for every test so the suite is network-free and
needs no API keys. Each node's fake-path returns canned values; the
graphs run end-to-end with hardcoded chunks (per L2 + Phase A).
"""

from __future__ import annotations

import importlib
from dataclasses import replace

import pytest


@pytest.fixture(autouse=True)
def _force_fake_backend(monkeypatch):
    """Replace `settings.llm.backend` with 'fake' in every module that
    imported `from src.config import settings`. Frozen dataclasses can't
    be mutated, so we build a new Settings and patch each reference.
    """
    from src import config as cfg

    fake_llm = replace(cfg.settings.llm, backend="fake")
    fake_settings = replace(cfg.settings, llm=fake_llm)
    monkeypatch.setattr("src.config.settings", fake_settings)

    for modpath in (
        "src.graph.client",
        "src.graph.nodes.intent",
        "src.graph.nodes.self_check",
        "src.graph.nodes.generate",
        "src.graph.nodes.decompose",
        "src.graph.nodes.rewrite",
        "src.graph.nodes.chat",
    ):
        try:
            mod = importlib.import_module(modpath)
        except ImportError:
            continue
        if hasattr(mod, "settings"):
            monkeypatch.setattr(f"{modpath}.settings", fake_settings)

    return fake_settings


@pytest.fixture
def stub_chunks():
    """The 3 hardcoded retrieve() chunks — re-export for direct tests."""
    from src.graph.nodes.retrieve import _STUB_CHUNKS

    return list(_STUB_CHUNKS)


@pytest.fixture
def make_task_state():
    """Build a TaskState with sane defaults; override via kwargs."""
    from src.graph.state import initial_task_state

    def _factory(**overrides):
        base = {
            "grade": 7,
            "subject": "islamic_studies",
            "standalone_question": "What is photosynthesis?",
            "language": "en",
        }
        base.update(overrides)
        return initial_task_state(**base)

    return _factory


@pytest.fixture
def make_outer_state():
    """Build an OuterState with sane defaults; override via kwargs."""
    from src.graph.state import initial_outer_state

    def _factory(**overrides):
        base = {
            "grade": 7,
            "subject": "islamic_studies",
            "user_query": "What is photosynthesis?",
        }
        base.update(overrides)
        return initial_outer_state(**base)

    return _factory
