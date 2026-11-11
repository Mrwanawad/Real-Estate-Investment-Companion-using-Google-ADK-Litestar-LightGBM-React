import pytest


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """GEMINI_API_KEY is set system-wide on dev machines; tests must never reach a real LLM."""
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
