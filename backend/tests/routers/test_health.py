import asyncio
import time
from unittest.mock import AsyncMock, patch


async def test_health_all_ok(client):
    with (
        patch("app.routers.health.check_db", new=AsyncMock(return_value=True)),
        patch("app.routers.health.check_redis", new=AsyncMock(return_value=True)),
    ):
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_db_down(client):
    with (
        patch("app.routers.health.check_db", new=AsyncMock(return_value=False)),
        patch("app.routers.health.check_redis", new=AsyncMock(return_value=True)),
    ):
        r = await client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "error"}


async def test_health_redis_down(client):
    with (
        patch("app.routers.health.check_db", new=AsyncMock(return_value=True)),
        patch("app.routers.health.check_redis", new=AsyncMock(return_value=False)),
    ):
        r = await client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "error"}


async def test_health_both_down(client):
    with (
        patch("app.routers.health.check_db", new=AsyncMock(return_value=False)),
        patch("app.routers.health.check_redis", new=AsyncMock(return_value=False)),
    ):
        r = await client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "error"}


async def test_health_probes_run_concurrently(client):
    async def slow_true() -> bool:
        await asyncio.sleep(3.0)
        return True

    with (
        patch("app.routers.health.check_db", new=slow_true),
        patch("app.routers.health.check_redis", new=slow_true),
    ):
        start = time.perf_counter()
        r = await client.get("/health")
        elapsed = time.perf_counter() - start
    assert r.status_code == 200
    assert elapsed < 5.0


async def test_api_health_alias_does_not_exist(client):
    r = await client.get("/api/health")
    assert r.status_code == 404
