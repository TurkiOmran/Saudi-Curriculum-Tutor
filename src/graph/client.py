"""LLM client factory.

One entry point — `get_llm(temperature=...)` — returns a LangChain
`BaseChatModel`. Nodes call `.ainvoke()` / `.astream()` /
`.with_structured_output()` on it; they never import a specific provider.

Backends (L3, L17, L20):
  - `fake`       — FakeListChatModel, no network, no API key. Phase-A default.
  - `openrouter` — ChatOpenAI pointed at openrouter.ai, wrapped with the
                   L20 transient-retry policy (3 tries, exponential jitter,
                   only transient HTTP / connection / timeout classes).
  - `ollama`     — placeholder. Wire up when local target is decided.

Swapping backends is a single line in `config.yaml`.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import Runnable

from src.config import settings

# Canned responses for the `fake` backend. Phase-A nodes return canned
# values directly (bypassing the LLM), so these only fire if a Phase-B+
# node is invoked while backend=fake.
_FAKE_RESPONSES = [
    "stubbed answer [1]",
]


def _transient_exceptions() -> tuple[type[BaseException], ...]:
    """Exception types eligible for retry per L20.

    Importing lazily so the openai dep is only required when the
    openrouter backend is actually selected.
    """
    from openai import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        RateLimitError,
    )

    return (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


def get_llm(temperature: float | None = None) -> BaseChatModel | Runnable:
    """Return a chat model configured for the current backend.

    `temperature` overrides the per-backend default; pass
    `settings.llm.classifier_temperature` for deterministic nodes and
    `settings.llm.generation_temperature` for the generate node.

    The returned value is a `BaseChatModel` for `fake`, or a retry-wrapped
    `Runnable` for `openrouter`. Both expose `.ainvoke`, `.astream`, and
    `.with_structured_output` — nodes treat them interchangeably.
    """
    backend = settings.llm.backend

    if backend == "fake":
        return FakeListChatModel(responses=_FAKE_RESPONSES)

    if backend == "openrouter":
        from langchain_openai import ChatOpenAI

        if not settings.openrouter_api_key:
            raise RuntimeError(
                "llm.backend=openrouter requires OPENROUTER_API_KEY in .env"
            )

        temp = (
            temperature
            if temperature is not None
            else settings.llm.classifier_temperature
        )
        llm = ChatOpenAI(
            model=settings.llm.openrouter.model,
            base_url=settings.llm.openrouter.base_url,
            api_key=settings.openrouter_api_key,
            temperature=temp,
            max_tokens=settings.llm.max_tokens,
            timeout=settings.llm.timeout_seconds,
        )
        return llm.with_retry(
            retry_if_exception_type=_transient_exceptions(),
            stop_after_attempt=3,
            wait_exponential_jitter=True,
        )

    if backend == "ollama":
        raise NotImplementedError(
            "Ollama backend not yet implemented. "
            "Set `llm.backend: fake` or `openrouter` in config.yaml."
        )

    raise ValueError(f"Unknown llm.backend: {backend!r}")
