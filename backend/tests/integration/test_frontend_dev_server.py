"""Integration tests for the Vite dev server, its proxy to the backend, and
frontend-source-level wiring (TanStack Query, HealthResponse type).

Implements C4–C5, B3–B4, and G4 from `docs/iteration-0/0c-skeletons-qa.md`.
"""

from __future__ import annotations

import re

import httpx

from ._helpers import BACKEND_URL, FRONTEND_URL, REPO_ROOT


def test_T_C4_frontend_vite_reachable_from_host() -> None:
    r = httpx.get(f"{FRONTEND_URL}/", timeout=10.0)
    assert r.status_code == 200, r.text
    body = r.text
    assert "/@vite/client" in body or 'type="module"' in body, body[:500]


def test_T_C5_vite_proxy_forwards_health() -> None:
    r_proxy = httpx.get(f"{FRONTEND_URL}/health", timeout=10.0)
    r_direct = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
    assert r_proxy.status_code == 200
    assert r_direct.status_code == 200
    assert r_proxy.json() == r_direct.json()
    # Source check: frontend code must not reference in-docker hostname.
    matches: list[str] = []
    for path in (REPO_ROOT / "frontend" / "src").rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "backend:8000" in text:
            matches.append(str(path.relative_to(REPO_ROOT)))
    assert matches == [], f"frontend src must not contain 'backend:8000': {matches}"


def test_T_B3_tanstack_query_provider_and_useQuery() -> None:
    src = REPO_ROOT / "frontend" / "src"
    text_all = "\n".join(p.read_text(encoding="utf-8") for p in src.rglob("*.tsx") if p.is_file())
    text_all += "\n" + "\n".join(p.read_text(encoding="utf-8") for p in src.rglob("*.ts") if p.is_file())
    assert "QueryClientProvider" in text_all, "QueryClientProvider not present in frontend/src"
    assert "useQuery" in text_all, "useQuery not used in frontend/src"


def test_T_B4_health_response_type_matches_contracts() -> None:
    types_dir = REPO_ROOT / "frontend" / "src" / "types"
    matches = [p for p in types_dir.rglob("*.ts") if "HealthResponse" in p.read_text(encoding="utf-8")]
    assert matches, "HealthResponse interface not declared in frontend/src/types"
    text = "\n".join(p.read_text(encoding="utf-8") for p in matches)
    # exact field set
    assert re.search(r'status:\s*"ok"\s*\|\s*"error"', text), "status union must be 'ok' | 'error'"
    # No extra fields beyond status.
    iface_match = re.search(r"interface\s+HealthResponse\s*\{([^}]*)\}", text)
    assert iface_match
    body = iface_match.group(1)
    declared = re.findall(r"^\s*(\w+)\s*:", body, re.M)
    assert set(declared) == {"status"}, f"unexpected fields: {declared}"
    # Consumer must annotate the fetch result as HealthResponse, not any.
    consumer_text = (REPO_ROOT / "frontend" / "src" / "hooks" / "useHealth.ts").read_text(encoding="utf-8")
    assert "HealthResponse" in consumer_text
    assert "any" not in re.findall(r"<\s*([A-Za-z_$][\w$]*)\s*[,>]", consumer_text)


def test_T_G4_vite_proxy_target_matches_compose_backend() -> None:
    vite = (REPO_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    targets = re.findall(r'target:\s*"([^"]+)"', vite)
    assert targets, "no proxy target in vite.config.ts"
    for t in targets:
        assert t == "http://backend:8000", f"vite proxy target must be http://backend:8000 (got {t})"
    compose_yaml = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(r"^\s*backend:\s*$", compose_yaml, re.M)
    assert re.search(r'"?\s*8000:8000\s*"?', compose_yaml), "backend must publish 8000:8000"
