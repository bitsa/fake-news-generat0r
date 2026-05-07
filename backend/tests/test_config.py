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
