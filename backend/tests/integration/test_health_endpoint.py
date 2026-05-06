"""Integration tests for the /health endpoint: shape, real connectivity probes,
error-state HTTP mapping, and recovery without backend restart.

Implements groups A and the health-related slices of group G from
`docs/iteration-0/0c-skeletons-qa.md`.
"""

from __future__ import annotations

import re
import subprocess
import time

import httpx

from ._helpers import (
    BACKEND_URL,
    HEALTH_RESPONSE_BUDGET_S,
    REPO_ROOT,
    compose,
    wait_for_healthy,
    wait_for_health_endpoint_ok,
)


# ---------- A. /health real connectivity ----------


def test_T_A1_health_ok_shape() -> None:
    r = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"status": "ok"}, body
    assert set(body.keys()) == {"status"}, body
    assert isinstance(body["status"], str)


def _exercise_dependency_down(stop_services: list[str], expected_body: dict) -> None:
    try:
        for svc in stop_services:
            compose("stop", svc)
        # Give the backend a moment to notice (pool checks happen on next request).
        time.sleep(2)
        start = time.perf_counter()
        r = httpx.get(f"{BACKEND_URL}/health", timeout=HEALTH_RESPONSE_BUDGET_S + 1.0)
        elapsed = time.perf_counter() - start
        assert r.status_code == 503, f"expected 503, got {r.status_code}, body={r.text}"
        assert r.json() == expected_body, r.json()
        assert elapsed <= HEALTH_RESPONSE_BUDGET_S, f"/health took {elapsed:.2f}s (budget {HEALTH_RESPONSE_BUDGET_S}s)"
    finally:
        for svc in stop_services:
            compose("start", svc, check=False)
            wait_for_healthy(svc)
        wait_for_health_endpoint_ok()


def test_T_A2_postgres_down_returns_503_within_5s() -> None:
    _exercise_dependency_down(["postgres"], {"status": "error"})


def test_T_A3_redis_down_returns_503_within_5s() -> None:
    _exercise_dependency_down(["redis"], {"status": "error"})


def test_T_A4_both_down_returns_503() -> None:
    _exercise_dependency_down(["postgres", "redis"], {"status": "error"})


def test_T_A5_recovery_without_backend_restart() -> None:
    """Stop postgres → recover → /health 200; backend container StartedAt must not change."""

    def inspect_started_at() -> str:
        container_id = compose("ps", "-q", "backend").stdout.strip()
        assert container_id, "could not resolve backend container id via `docker compose ps -q backend`"
        out = subprocess.run(
            ["docker", "inspect", container_id, "--format", "{{.State.StartedAt}}"],
            text=True, capture_output=True, check=True,
        )
        return out.stdout.strip()

    started_at_before = inspect_started_at()
    try:
        compose("stop", "postgres")
        time.sleep(1)
        r = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
        assert r.status_code == 503
    finally:
        compose("start", "postgres")
        wait_for_healthy("postgres")
    # next call should recover (allowing one stale-pool retry per spec edge case 3)
    body = wait_for_health_endpoint_ok(timeout=15.0)
    assert body == {"status": "ok"}
    started_at_after = inspect_started_at()
    assert started_at_before == started_at_after, (
        f"backend container restarted across kill/recover: {started_at_before!r} -> {started_at_after!r}"
    )


# T-A6 is satisfied by T-A2 + T-A3 passing — see QA plan.


# ---------- G. Cross-contract consistency (health-related) ----------


def test_T_G1_health_shape_matches_contracts_typescript_type() -> None:
    contracts = (REPO_ROOT / "contracts.md").read_text(encoding="utf-8")
    iface = re.search(r"interface\s+HealthResponse\s*\{([^}]*)\}", contracts)
    assert iface, "HealthResponse interface missing from contracts.md"
    body = iface.group(1)
    fields = set(re.findall(r"^\s*(\w+)\s*:", body, re.M))
    assert fields == {"status"}
    # Live shape
    r = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
    assert set(r.json().keys()) == fields


def test_T_G2_state_to_http_mapping() -> None:
    # 200 healthy verified by T-A1; 503 verified by T-A2..T-A4. Re-check 200 here.
    r = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
