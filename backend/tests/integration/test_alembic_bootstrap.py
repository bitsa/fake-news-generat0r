"""Integration tests for the Alembic bootstrap surface installed in 0.C.

Implements group E (E1–E4) from `docs/iteration-0/0c-skeletons-qa.md`. These
tests assert only that Alembic is wired up and runnable; the first migration
itself lands in task 1.1 and is verified by the migration QA suite.
"""

from __future__ import annotations

import re

from ._helpers import REPO_ROOT, compose


def test_T_E1_alembic_ini_present_and_points_at_migrations() -> None:
    ini = REPO_ROOT / "backend" / "alembic.ini"
    assert ini.exists()
    text = ini.read_text(encoding="utf-8")
    assert re.search(r"^\s*script_location\s*=\s*migrations\s*$", text, re.M), (
        "alembic.ini script_location must be 'migrations'"
    )


def test_T_E2_env_py_async_configured() -> None:
    env_py = (REPO_ROOT / "backend" / "migrations" / "env.py").read_text(encoding="utf-8")
    assert re.search(r"async_engine_from_config|create_async_engine|AsyncEngine", env_py), (
        "env.py must use async SQLAlchemy engine"
    )
    assert "run_sync" in env_py, "env.py must run migrations through connection.run_sync"


def test_T_E3_versions_dir_present() -> None:
    versions = REPO_ROOT / "backend" / "migrations" / "versions"
    assert versions.is_dir(), f"missing migrations/versions directory: {versions}"


def test_T_E4_alembic_current_runs_clean() -> None:
    out = compose("exec", "-T", "backend", "alembic", "current", check=False)
    assert out.returncode == 0, f"alembic current failed: rc={out.returncode}\nstdout={out.stdout}\nstderr={out.stderr}"
    text = (out.stdout or "") + (out.stderr or "")
    assert re.search(r"\bERROR\b", text, re.IGNORECASE) is None, text
