from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    # SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@localhost:5432/reic
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/reic"

    # fake: scripted model for tests and offline demos.
    llm_provider: Literal["anthropic", "gemini", "fake"] = "fake"
    anthropic_model: str = "claude-sonnet-5-5"
    gemini_model: str = "gemini-3.5-flash"
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    embedder: Literal["hashing", "minilm", "bge-m3"] = "hashing"

    # Broker handoff: the broker queue API key and the signed webhook.
    broker_api_key: SecretStr | None = None
    webhook_url: str | None = None
    webhook_secret: SecretStr | None = None

    # Financing and scenario assumptions (fractions). Synthetic defaults, shown in outputs.
    discount_rate: float = 0.22
    mortgage_rate: float = 0.24
    mortgage_years: int = 10
    inflation_mean: float = 0.15

    cors_origins: list[str] = ["http://localhost:5173"]
    # Per-client limit on POST /leads and chat session/message creation; 0 disables.
    rate_limit_per_minute: int = 20
    # Header a trusted proxy sets to the real client IP (Fly-Client-IP on Fly.io).
    client_ip_header: str | None = None
    otel_enabled: bool = False
