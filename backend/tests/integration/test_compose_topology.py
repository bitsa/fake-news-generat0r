"""Integration tests for docker-compose topology and the backend container's
runtime surface (real uvicorn, OpenAPI exposed).

Implements group C tests C1–C3 from `docs/iteration-0/0c-skeletons-qa.md`.
"""

from __future__ import annotations

import json
import re
import time

import httpx

from ._helpers import BACKEND_URL, REPO_ROOT, compose


def test_T_C1_owned_services_running_no_crashloop() -> None:
    owned = {"postgres", "redis", "backend", "frontend"}
    statuses_per_poll: list[dict[str, str]] = []
    for _ in range(3):
        out = compose("ps", "--format", "json").stdout
        snapshot: dict[str, str] = {}
        for row in json.loads(out or "[]"):
            snapshot[row.get("Service", "")] = row.get("State", "")
        statuses_per_poll.append(snapshot)
        time.sleep(5)
    for snapshot in statuses_per_poll:
        for svc in owned:
            assert svc in snapshot, f"{svc} missing from compose ps; saw {snapshot}"
            assert snapshot[svc] == "running", f"{svc} not running: {snapshot[svc]}"
            assert snapshot[svc] != "restarting", f"{svc} restarting (crash-loop?)"
    # worker must be present but is not asserted on
    for snapshot in statuses_per_poll:
        assert "worker" in snapshot, "worker service missing from compose"


def test_T_C2_backend_depends_on_healthy() -> None:
    compose_yaml = (REPO_ROOT / "docker-compose.yml").read_text()
    backend_block = re.search(r"\n  backend:\n(.*?)(?=\n  \w+:|\Z)", compose_yaml, re.S)
    assert backend_block, "could not locate backend service block in docker-compose.yml"
    block = backend_block.group(1)
    assert "depends_on" in block
    assert re.search(
        r"postgres:\s*\n\s*condition:\s*service_healthy", block
    ), "backend.depends_on.postgres must specify condition: service_healthy"
    assert re.search(
        r"redis:\s*\n\s*condition:\s*service_healthy", block
    ), "backend.depends_on.redis must specify condition: service_healthy"


def test_T_C3_real_uvicorn_and_openapi() -> None:
    r = httpx.head(f"{BACKEND_URL}/health", timeout=5.0)
    server_hdr = r.headers.get("server", "").lower()
    assert "uvicorn" in server_hdr, f"server header missing uvicorn: {r.headers}"
    r2 = httpx.get(f"{BACKEND_URL}/openapi.json", timeout=5.0)
    assert r2.status_code == 200
    spec = r2.json()
    assert "openapi" in spec
    assert "/health" in spec.get("paths", {})
