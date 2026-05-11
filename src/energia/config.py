"""Application settings loaded from environment variables and optional .env file.

All settings have safe defaults so the package imports cleanly without a .env
present. ANTHROPIC_API_KEY defaults to empty string; any actual LLM call will
fail with an authentication error if it is not set — that is the correct
behaviour.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key. Required for LLM calls. Set in .env.",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-6",
        description="Anthropic model ID used by the chatbot.",
    )
    aneel_base_url: str = Field(
        default="https://dadosabertos.aneel.gov.br/api/3/action",
        description="ANEEL open-data REST API base URL.",
    )
    duckdb_path: str = Field(
        default="data/energia.duckdb",
        description="Filesystem path to the local DuckDB file (gitignored).",
    )
    session_token_budget: int = Field(
        default=200_000,
        description=(
            "Per-session Anthropic token budget (HR-7). "
            "The orchestrator halts with a graceful error at this threshold."
        ),
    )
    tariff_fallback_path: str = Field(
        default="data/tariff_fallback_b1.csv",
        description=(
            "Path to the offline B1 tariff CSV. "
            "Built in Sprint 2 Task 2.1; does not need to exist at import time."
        ),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()
