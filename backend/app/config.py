"""Application settings loaded from environment."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SentinelAI"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./sentinelai.db"

    # Checkpointing
    checkpoint_db_path: str = "./checkpoints.db"

    # LLM providers (empty keys → demo/mock mode)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Routing defaults
    default_cost_ceiling_usd: float = 0.05
    provider_timeout_seconds: float = 30.0
    max_reflection_retries: int = 2

    # Models
    openai_fast_model: str = "gpt-4o-mini"
    openai_strong_model: str = "gpt-4o"
    anthropic_fast_model: str = "claude-3-5-haiku-20241022"
    anthropic_strong_model: str = "claude-sonnet-4-20250514"
    gemini_fast_model: str = "gemini-2.0-flash"
    gemini_strong_model: str = "gemini-2.0-flash"

    # RAG
    chroma_persist_dir: str = "./chroma_data"
    docs_dir: str = "./data/docs"
    embedding_model: str = "text-embedding-3-small"
    rag_top_k: int = 4

    # Guardrails
    prompt_injection_threshold: float = 0.65
    min_confidence_for_auto_reply: float = 0.45
    faithfulness_threshold: float = 0.5

    # Observability
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "sentinelai-gateway"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def demo_mode(self) -> bool:
        """True when no real provider keys are configured."""
        return not any([self.openai_api_key, self.anthropic_api_key, self.google_api_key])


@lru_cache
def get_settings() -> Settings:
    return Settings()
