"""Central configuration.

Every tunable lives here and is sourced from the environment, so that a
deployment can be re-pointed (local models -> free tier -> paid API) without
touching agent code.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelRole(StrEnum):
    """What a model is being asked to do, independent of who supplies it.

    Agents request a role; the registry resolves the role to a concrete
    provider and model. This indirection is what keeps provider choice out of
    agent code.
    """

    REASONING = "reasoning"
    """Multi-step analysis: extraction, conflict adjudication, compliance mapping."""

    FAST = "fast"
    """High-volume, low-difficulty calls: classification, routing, short structured output."""

    EMBEDDING = "embedding"
    """Dense vector generation for retrieval."""


class ModelSpec(BaseSettings):
    """A resolved `provider:model` pair."""

    provider: str
    model: str

    @classmethod
    def parse(cls, raw: str) -> ModelSpec:
        """Parse a `provider:model` string.

        The model half may itself contain colons (Ollama tags such as
        `qwen3:8b`), so only the first colon is a separator.
        """
        provider, sep, model = raw.partition(":")
        if not sep or not model:
            raise ValueError(
                f"Invalid model spec {raw!r}; expected 'provider:model' "
                f"(e.g. 'ollama:qwen3:8b' or 'gemini:gemini-2.0-flash')"
            )
        return cls(provider=provider.strip().lower(), model=model.strip())

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.provider}:{self.model}"


class Settings(BaseSettings):
    """Application settings, loaded from environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="local", alias="NYAYA_ENV")
    log_level: str = Field(default="INFO", alias="NYAYA_LOG_LEVEL")

    # --- database ---
    postgres_user: str = "nyaya"
    postgres_password: str = "nyaya_dev_pw"
    postgres_db: str = "nyaya"
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    # --- llm routing (raw strings; parsed via `model_for`) ---
    llm_reasoning: str = Field(default="ollama:qwen3:8b", alias="NYAYA_LLM_REASONING")
    llm_fast: str = Field(default="ollama:llama3.1:8b", alias="NYAYA_LLM_FAST")
    llm_embedding: str = Field(default="ollama:bge-m3", alias="NYAYA_LLM_EMBEDDING")

    # --- provider credentials ---
    google_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- retrieval ---
    retrieval_top_k: int = Field(default=40, alias="NYAYA_RETRIEVAL_TOP_K")
    rerank_top_n: int = Field(default=8, alias="NYAYA_RERANK_TOP_N")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", alias="NYAYA_RERANKER_MODEL")
    nli_model: str = Field(
        default="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli", alias="NYAYA_NLI_MODEL"
    )

    # --- observability ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """SQLAlchemy async connection URL."""
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Synchronous URL, used by Alembic and the LangGraph checkpointer."""
        return self.database_url.replace("postgresql+psycopg", "postgresql")

    def model_for(self, role: ModelRole) -> ModelSpec:
        """Resolve a model role to a concrete provider and model."""
        raw = {
            ModelRole.REASONING: self.llm_reasoning,
            ModelRole.FAST: self.llm_fast,
            ModelRole.EMBEDDING: self.llm_embedding,
        }[role]
        return ModelSpec.parse(raw)


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton."""
    return Settings()
