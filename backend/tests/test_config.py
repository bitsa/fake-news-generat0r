import importlib
import os
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_settings_reads_env_vars(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")

    import app.config as config_module

    importlib.reload(config_module)
    s = config_module.Settings()
    assert s.database_url == "postgresql+asyncpg://u:p@h/db"
    assert s.redis_url == "redis://h:6379/1"
    assert s.openai_api_key == "sk-xyz"


def test_settings_raises_when_required_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from app.config import Settings

    with pytest.raises(ValidationError):
        # Fields are populated from env at runtime; Pylance can't see that.
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_no_os_environ_outside_config_module():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text(encoding="utf-8")
        if any(
            pat in text
            for pat in (
                "os.environ",
                "os.getenv",
                "from os import getenv",
                "getenv(",
            )
        ):
            offenders.append(str(path.relative_to(app_dir.parent)))
    assert (
        offenders == []
    ), f"os.environ/getenv found outside app/config.py: {offenders}"


def test_settings_openai_request_timeout_seconds_defaults_to_30(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("OPENAI_REQUEST_TIMEOUT_SECONDS", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    s = config_module.Settings()
    assert s.openai_request_timeout_seconds == 30


def test_settings_openai_request_timeout_seconds_rejects_zero_or_negative(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")

    from app.config import Settings

    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]

    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "-5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_openai_mock_mode_defaults_to_false(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("OPENAI_MOCK_MODE", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    s = config_module.Settings()
    assert s.openai_mock_mode is False


def test_env_example_documents_openai_request_timeout_seconds():
    env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "OPENAI_REQUEST_TIMEOUT_SECONDS" in text


def test_env_example_documents_openai_mock_mode():
    env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "OPENAI_MOCK_MODE" in text


def test_settings_chat_llm_mock_defaults_to_true(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("CHAT_LLM_MOCK", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    s = config_module.Settings()
    assert s.chat_llm_mock is True


def test_settings_chat_history_window_defaults_to_10(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("CHAT_HISTORY_WINDOW", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    s = config_module.Settings()
    assert s.chat_history_window == 10


def test_settings_chat_history_window_rejects_zero_or_negative(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")

    from app.config import Settings

    monkeypatch.setenv("CHAT_HISTORY_WINDOW", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]

    monkeypatch.setenv("CHAT_HISTORY_WINDOW", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_chat_max_output_tokens_defaults_to_512(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("CHAT_MAX_OUTPUT_TOKENS", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    s = config_module.Settings()
    assert s.chat_max_output_tokens == 512


def test_settings_chat_max_output_tokens_rejects_zero_or_negative(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")

    from app.config import Settings

    monkeypatch.setenv("CHAT_MAX_OUTPUT_TOKENS", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]

    monkeypatch.setenv("CHAT_MAX_OUTPUT_TOKENS", "-10")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_chat_llm_module_does_not_introduce_chat_model_or_chat_temperature_fields():
    from app.config import Settings

    fields = Settings.model_fields
    assert "openai_model_chat" in fields
    assert "openai_temperature_chat" in fields
    assert "chat_model" not in fields
    assert "chat_temperature" not in fields


def test_env_example_documents_chat_llm_mock():
    env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "CHAT_LLM_MOCK" in text


def test_env_example_documents_chat_history_window():
    env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "CHAT_HISTORY_WINDOW" in text


def test_env_example_documents_chat_max_output_tokens():
    env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "CHAT_MAX_OUTPUT_TOKENS" in text


def test_env_example_pre_existing_openai_keys_are_unchanged_by_chat_llm_task():
    env_example = Path(__file__).resolve().parent.parent.parent / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    # Each pre-existing line must appear byte-identical to its committed form.
    expected_lines = {
        "OPENAI_API_KEY=sk-REPLACE_ME  # OpenAI API key. Never log this"
        " value. Replace before running.",
        "OPENAI_MODEL_CHAT=gpt-4o-mini  # Model used by the chat endpoint.",
        "OPENAI_TEMPERATURE_CHAT=0.7  # Temperature for chat responses.",
        "OPENAI_REQUEST_TIMEOUT_SECONDS=30  # Per-request timeout for"
        " the OpenAI client (seconds).",
        "OPENAI_MOCK_MODE=true  # If true, uses mock OpenAI responses"
        " for testing without API calls. Set to false to use real API.",
    }
    lines = set(text.splitlines())
    missing = expected_lines - lines
    assert not missing, f"chat-llm task altered pre-existing OpenAI lines: {missing}"


def test_dedup_window_hours_default_is_168_and_must_be_positive(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("DEDUP_WINDOW_HOURS", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.Settings().dedup_window_hours == 168

    from app.config import Settings

    monkeypatch.setenv("DEDUP_WINDOW_HOURS", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setenv("DEDUP_WINDOW_HOURS", "-1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_dedup_jaccard_high_default_is_080_and_within_zero_one(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("DEDUP_JACCARD_HIGH", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.Settings().dedup_jaccard_high == 0.80

    from app.config import Settings

    monkeypatch.setenv("DEDUP_JACCARD_HIGH", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setenv("DEDUP_JACCARD_HIGH", "1.5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_dedup_jaccard_floor_default_is_040_and_within_zero_one(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("DEDUP_JACCARD_FLOOR", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.Settings().dedup_jaccard_floor == 0.40

    from app.config import Settings

    monkeypatch.setenv("DEDUP_JACCARD_FLOOR", "-0.1")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setenv("DEDUP_JACCARD_FLOOR", "1.5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_dedup_cosine_threshold_default_is_088_and_within_zero_one(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("DEDUP_COSINE_THRESHOLD", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.Settings().dedup_cosine_threshold == 0.88

    from app.config import Settings

    monkeypatch.setenv("DEDUP_COSINE_THRESHOLD", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
    monkeypatch.setenv("DEDUP_COSINE_THRESHOLD", "1.01")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_openai_model_embedding_default_is_text_embedding_3_small(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xyz")
    monkeypatch.delenv("OPENAI_MODEL_EMBEDDING", raising=False)

    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.Settings().openai_model_embedding == "text-embedding-3-small"


def test_clean_module_state_after():
    """Restore the singleton module after monkeypatched env reloads above."""
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://test:test@localhost:5432/test"
        )
    if "REDIS_URL" not in os.environ:
        os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    if "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = "sk-test-placeholder"
    import app.config as config_module

    importlib.reload(config_module)
    assert config_module.settings is not None
