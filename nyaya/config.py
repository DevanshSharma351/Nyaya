"""Central configuration.

Every tunable lives here and is sourced from the environment, so that a
deployment can be re-pointed (local models -> free tier -> paid API) without
touching agent code.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import BaseModel, Field, PostgresDsn, computed_field
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


class ModelSpec(BaseModel):
    """A resolved `provider:model` pair.

    Deliberately a plain `BaseModel`, not `BaseSettings`. As a settings class it
    would treat `provider` and `model` as environment-backed fields, so a stray
    `PROVIDER` or `MODEL` variable in the environment would silently populate a
    spec that was never parsed from configuration.
    """

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)

    @classmethod
    def parse(cls, raw: str) -> ModelSpec:
        """Parse a `provider:model` string.

        The model half may itself contain colons (Ollama tags such as
        `qwen3:8b`), so only the first colon is a separator.
        """
        provider, sep, model = raw.partition(":")
        if not sep or not model.strip() or not provider.strip():
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

    # --- api ---
    # Origins allowed to call the API from a browser. Listed rather than
    # wildcarded: this API returns compliance findings and must not be readable
    # from an arbitrary page. It is configurable because the frontend origin is
    # a deployment fact, not a constant - hardcoding :3000 meant a production
    # build served on any other port could not reach its own backend, which is
    # exactly how it failed the first time it was served from one.
    # 3000 is `next dev`, 3100 is a local production build. Both are localhost
    # and neither is a deployment origin, so listing them by default costs
    # nothing and removes a failure that looks exactly like the API being down:
    # a browser CORS rejection surfaces to fetch() as "Failed to fetch", with no
    # indication that the server answered perfectly well.
    cors_origins: str = Field(
        default=(
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:3100,http://127.0.0.1:3100"
        ),
        alias="NYAYA_CORS_ORIGINS",
    )

    @property
    def allowed_origins(self) -> list[str]:
        """`cors_origins` split into a list, blanks discarded."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
    ollama_timeout_seconds: float = Field(
        default=240.0,
        alias="NYAYA_OLLAMA_TIMEOUT_SECONDS",
        description=(
            "How long to wait for one generation. Sized below a typical "
            "browser or proxy timeout so a slow model surfaces as a handled "
            "error rather than a connection the client gives up on first."
        ),
    )
    ollama_context_tokens: int = Field(
        default=8192,
        alias="NYAYA_OLLAMA_CONTEXT_TOKENS",
        description=(
            "Context window requested from Ollama. Its own default of 4096 is "
            "too small - the extraction prompt, the schema grammar and a long "
            "answer do not fit, and it truncates silently. 8192 holds all of "
            "them; larger only grows the KV cache, which on a shared GPU costs "
            "throughput for context nothing uses."
        ),
    )

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
