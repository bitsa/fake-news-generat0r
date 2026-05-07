"""Integration tests for configuration discipline and secret hygiene.

Implements group D (D1–D4) and the env-var slice of group G (G3) from
`docs/iteration-0/0c-skeletons-qa.md`.
"""

from __future__ import annotations

import re

import httpx

from ._helpers import BACKEND_URL, REPO_ROOT, compose


def test_T_D1_no_os_environ_outside_config() -> None:
    backend_app = REPO_ROOT / "backend" / "app"
    offenders: list[str] = []
    for path in backend_app.rglob("*.py"):
        if path.name == "config.py":
            continue
        text = path.read_text(encoding="utf-8")
        if (
            re.search(r"\bos\.environ\b", text)
            or re.search(r"\bos\.getenv\b", text)
            or re.search(
                r"^\s*from\s+os\s+import\s+[^\n]*\b(getenv|environ)\b", text, re.M
            )
        ):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"os.environ/getenv outside config.py: {offenders}"


def _backend_env(var: str) -> str:
    """Read an env var value as the backend container actually sees it at runtime."""
    out = compose("exec", "-T", "backend", "printenv", var, check=False)
    return (out.stdout or "").strip()


def test_T_D4_secret_value_not_in_logs() -> None:
    for _ in range(3):
        httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
    logs = compose("logs", "--no-color", "backend").stdout

    forbidden: list[tuple[str, str]] = []

    api_key = _backend_env("OPENAI_API_KEY")
    if api_key:
        forbidden.append(("OPENAI_API_KEY", api_key))

    database_url = _backend_env("DATABASE_URL")
    if database_url:
        forbidden.append(("DATABASE_URL", database_url))
        # Also flag the password segment in isolation, in case the URL gets
        # parsed/rebuilt.
        m = re.search(r"://[^:/@\s]+:([^@\s]+)@", database_url)
        if m:
            forbidden.append(("DATABASE_URL password", m.group(1)))

    assert (
        forbidden
    ), "could not read OPENAI_API_KEY/DATABASE_URL from backend container"

    leaks = [(name, value) for name, value in forbidden if value in logs]
    assert (
        leaks == []
    ), f"secret values leaked in backend logs: {[name for name, _ in leaks]}"


