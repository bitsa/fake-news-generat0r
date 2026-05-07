"""Shared helpers for the docker-compose-driven integration suite.

These tests run against the live `docker compose up -d` stack from the repo
root: backend at http://localhost:8000, Vite dev server at http://localhost:5173.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"

DEPS_HEALTHY_TIMEOUT_S = 60
HEALTH_RESPONSE_BUDGET_S = 5.0


COMPOSE_DEFAULT_TIMEOUT_S = 120


def compose(
    *args: str,
    check: bool = True,
    capture: bool = True,
    timeout: float = COMPOSE_DEFAULT_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    cmd = ["docker", "compose", *args]
    try:
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            capture_output=capture,
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


def parse_compose_ps_json(out: str) -> list[dict]:
    """Parse `docker compose ps --format json` across CLI versions.

    Older CLIs emit a JSON array; newer ones emit a single object (when one
    service is targeted) or NDJSON (one object per line, multi-service).
    """
    out = (out or "").strip()
    if not out:
        return []
    try:
        parsed = json.loads(out)
    except json.JSONDecodeError:
        return [json.loads(line) for line in out.splitlines() if line.strip()]
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def wait_for_healthy(service: str, timeout: float = DEPS_HEALTHY_TIMEOUT_S) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = compose("ps", "--format", "json", service, check=False).stdout
        for row in parse_compose_ps_json(out):
            if row.get("Service") == service and row.get("Health") == "healthy":
                return
        time.sleep(1)
    raise AssertionError(f"Service {service} did not reach healthy in {timeout}s")


def wait_for_health_endpoint_ok(timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            r = httpx.get(
                f"{BACKEND_URL}/health",
                timeout=min(HEALTH_RESPONSE_BUDGET_S, remaining),
            )
            if r.status_code == 200 and r.json().get("status") == "ok":
                return r.json()
        except Exception as e:  # noqa: BLE001
            last_exc = e
        time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
    raise AssertionError(
        f"backend /health did not return 200/ok within {timeout}s: {last_exc!r}"
    )
