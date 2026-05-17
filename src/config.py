"""Config loader — reads `config.yaml` from the repo root + `.env` from anywhere.

One import, one settings object. Every module that needs a config value
imports `settings` from here, never re-parses the YAML.

Shape locked in `RESPONSE_WORKFLOW.md` L17.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config.yaml"

load_dotenv(REPO_ROOT / ".env")

Backend = Literal["fake", "openrouter", "ollama"]


@dataclass(frozen=True)
class OpenRouterConfig:
    model: str
    base_url: str


@dataclass(frozen=True)
class OllamaConfig:
    model: str
    base_url: str


@dataclass(frozen=True)
class LLMConfig:
    backend: Backend
    openrouter: OpenRouterConfig
    ollama: OllamaConfig
    classifier_temperature: float
    generation_temperature: float
    max_tokens: int
    timeout_seconds: int


@dataclass(frozen=True)
class FeatureFlags:
    history_rewrite_enabled: bool
    decomposition_enabled: bool


@dataclass(frozen=True)
class RetrievalConfig:
    top_k_retrieve: int
    top_k_rerank: int
    reranker_model: str


@dataclass(frozen=True)
class MemoryConfig:
    max_turns: int


@dataclass(frozen=True)
class IngestionConfig:
    embed_batch_size: int
    annotate_images: bool


@dataclass(frozen=True)
class Settings:
    llm: LLMConfig
    features: FeatureFlags
    retrieval: RetrievalConfig
    memory: MemoryConfig
    ingestion: IngestionConfig

    @property
    def openrouter_api_key(self) -> str | None:
        return os.environ.get("OPENROUTER_API_KEY")

    @property
    def mistral_api_key(self) -> str | None:
        return os.environ.get("MISTRAL_API_KEY")


def _load() -> Settings:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    llm = raw["llm"]
    return Settings(
        llm=LLMConfig(
            backend=llm["backend"],
            openrouter=OpenRouterConfig(**llm["openrouter"]),
            ollama=OllamaConfig(**llm["ollama"]),
            classifier_temperature=llm["classifier_temperature"],
            generation_temperature=llm["generation_temperature"],
            max_tokens=llm["max_tokens"],
            timeout_seconds=llm["timeout_seconds"],
        ),
        features=FeatureFlags(**raw["features"]),
        retrieval=RetrievalConfig(**raw["retrieval"]),
        memory=MemoryConfig(**raw["memory"]),
        ingestion=IngestionConfig(**raw["ingestion"]),
    )


settings: Settings = _load()
