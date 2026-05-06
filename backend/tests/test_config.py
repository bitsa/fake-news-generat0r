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
