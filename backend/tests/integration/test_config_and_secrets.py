"""Integration tests for configuration discipline and secret hygiene.

Implements group D (D1–D4) and the env-var slice of group G (G3) from
`docs/iteration-0/0c-skeletons-qa.md`.
"""

from __future__ import annotations

import re
import subprocess

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
            or re.search(r"^\s*from\s+os\s+import\s+[^\n]*\b(getenv|environ)\b", text, re.M)
        ):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"os.environ/getenv outside config.py: {offenders}"


def test_T_D2_env_var_names_match_contracts() -> None:
    config_text = (REPO_ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    expected_in_use_by_0c = {"DATABASE_URL", "REDIS_URL"}
    declared_lower = set(re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*:", config_text, re.M))
    declared_upper = {f.upper() for f in declared_lower}
    missing = expected_in_use_by_0c - declared_upper
    assert not missing, f"Settings missing env vars required by 0.C: {missing}"
    contracts_text = (REPO_ROOT / "contracts.md").read_text(encoding="utf-8")
    contract_vars = set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", contracts_text, re.M))
    extras = declared_upper - contract_vars - {"MODEL_CONFIG"}
    assert not extras, f"Settings declares vars not in contracts.md: {extras}"


def test_T_D3_no_committed_secrets() -> None:
    out = subprocess.run(
        ["git", "grep", "-nE", r"OPENAI_API_KEY\s*=\s*sk-[A-Za-z0-9_-]{10,}",
         "--", ":!.env.example", ":!*.md"],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
    )
    matches = [ln for ln in out.stdout.splitlines() if ln.strip()]
    tracked = subprocess.run(
        ["git", "ls-files", ".env"], cwd=REPO_ROOT, text=True, capture_output=True, check=False
    ).stdout.strip()
    assert tracked == "", f".env must not be tracked: {tracked}"
    assert matches == [], f"committed secret-shaped values: {matches}"
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env$", gitignore, re.M), ".env must be in .gitignore"


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
        # Also flag the password segment in isolation, in case the URL gets parsed/rebuilt.
        m = re.search(r"://[^:/@\s]+:([^@\s]+)@", database_url)
        if m:
            forbidden.append(("DATABASE_URL password", m.group(1)))

    assert forbidden, "could not read OPENAI_API_KEY/DATABASE_URL from backend container"

    leaks = [(name, value) for name, value in forbidden if value in logs]
    assert leaks == [], f"secret values leaked in backend logs: {[name for name, _ in leaks]}"


def test_T_G3_env_var_names_match_contracts() -> None:
    """Cross-contract framing of T-D2 — the same expectation viewed from contracts.md side."""
    config_text = (REPO_ROOT / "backend" / "app" / "config.py").read_text(encoding="utf-8")
    declared_upper = {f.upper() for f in re.findall(r"^\s*([a-z_][a-z0-9_]*)\s*:", config_text, re.M)}
    contracts_text = (REPO_ROOT / "contracts.md").read_text(encoding="utf-8")
    contract_vars = set(re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", contracts_text, re.M))
    required = {"DATABASE_URL", "REDIS_URL"}
    assert required <= declared_upper
    assert required <= contract_vars
