import pytest
from pydantic import ValidationError

from reic.shared.config import Settings


def test_defaults_are_safe_for_tests() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "fake"
    assert settings.embedder == "hashing"
    assert settings.anthropic_api_key is None
    assert settings.gemini_api_key is None
    assert settings.otel_enabled is False
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value")
    monkeypatch.setenv("CORS_ORIGINS", '["http://a.test","http://b.test"]')
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "secret-value"
    assert "secret-value" not in repr(settings)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_rejects_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
