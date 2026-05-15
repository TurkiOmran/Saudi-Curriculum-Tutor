"""LLM client factory.

One entry point — `get_llm(temperature=...)` — returns a LangChain
`BaseChatModel`. Nodes call `.ainvoke()` / `.astream()` /
`.with_structured_output()` on it; they never import a specific provider.

Backends (L3, L17, L20):
  - `fake`       — FakeListChatModel, no network, no API key. Phase-A default.
  - `openrouter` — ChatOpenAI pointed at openrouter.ai, wrapped with the
                   L20 transient-retry policy. Implemented in Phase B.
  - `ollama`     — placeholder. Wire up when local target is decided.

Swapping backends is a single line in `config.yaml`.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.config import settings

# Canned responses for the `fake` backend. Phase-A nodes return canned
# values directly (bypassing the LLM), so these only fire if a Phase-B+
# node is invoked while backend=fake.
_FAKE_RESPONSES = [
    "stubbed answer [1]",
]


def get_llm(temperature: float | None = None) -> BaseChatModel:
    """Return a chat model configured for the current backend.

    `temperature` overrides the per-backend default; pass
    `settings.llm.classifier_temperature` for deterministic nodes and
    `settings.llm.generation_temperature` for the generate node.
    """
    backend = settings.llm.backend

    if backend == "fake":
        return FakeListChatModel(responses=_FAKE_RESPONSES)

    if backend == "openrouter":
        # Phase B lands the real impl. Keeping the import lazy so Phase A
        # works without an OpenRouter API key.
        raise NotImplementedError(
            "OpenRouter backend ships in Phase B. "
            "Set `llm.backend: fake` in config.yaml for now."
        )

    if backend == "ollama":
        raise NotImplementedError(
            "Ollama backend not yet implemented. "
            "Set `llm.backend: fake` in config.yaml for now."
        )

    raise ValueError(f"Unknown llm.backend: {backend!r}")
