"""Integration-suite conftest: enforce a healthy stack before any test runs."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_URL = "http://localhost:8000"
DEPS_HEALTHY_TIMEOUT_S = 60


COMPOSE_DEFAULT_TIMEOUT_S = 30.0


def _compose(
    *args: str, check: bool = False, timeout: float = COMPOSE_DEFAULT_TIMEOUT_S
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["docker", "compose", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=check,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = (
            exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        )
        stdout = (
            exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        )
        raise AssertionError(
            f"`docker compose {' '.join(args)}` timed out after {timeout}s.\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"`docker compose {' '.join(args)}` failed (exit {exc.returncode}).\n"
            f"stdout:\n{exc.stdout or ''}\nstderr:\n{exc.stderr or ''}"
        ) from exc


def _wait_for_healthy(service: str, timeout: float = DEPS_HEALTHY_TIMEOUT_S) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = _compose("ps", "--format", "json", service).stdout
        for row in json.loads(out or "[]"):
            if row.get("Service") == service and row.get("Health") == "healthy":
                return
        time.sleep(1)
    raise AssertionError(f"Service {service} did not reach healthy in {timeout}s")


def _wait_for_health_endpoint_ok(timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            r = httpx.get(f"{BACKEND_URL}/health", timeout=min(5.0, remaining))
            if r.status_code == 200 and r.json().get("status") == "ok":
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    raise AssertionError(f"backend /health did not return 200/ok within {timeout}s")


@pytest.fixture(scope="module", autouse=True)
def stack_baseline():
    """Module-level baseline: compose stack must be up and healthy before tests run."""
    _wait_for_healthy("postgres")
    _wait_for_healthy("redis")
    _wait_for_health_endpoint_ok()
    yield
    _compose("start", "postgres", "redis", "backend", check=True)
