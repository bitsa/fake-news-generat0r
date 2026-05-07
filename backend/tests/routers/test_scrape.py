from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.arq_client import get_arq_pool
from app.db import get_session
from app.exceptions import ServiceUnavailableError
from app.models import Article
from app.services.scraper import IngestResult
from app.sources import Source


def _make_session_cm() -> tuple[MagicMock, AsyncMock]:
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_session


@pytest_asyncio.fixture
async def scrape_client(app):
    """Client with lifespan deps mocked and get_session dependency overridden."""
    mock_cm, _ = _make_session_cm()
    mock_arq_pool = AsyncMock()

    async def override_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = lambda: mock_arq_pool

    with (
        patch("app.main._run_migrations", new=AsyncMock()),
        patch(
            "app.main.arq_client.create_arq_pool",
            new=AsyncMock(return_value=mock_arq_pool),
        ),
        patch("app.main.arq_client.close_arq_pool", new=AsyncMock()),
        patch("app.main.AsyncSessionLocal", return_value=mock_cm),
        patch("app.main.transformer.recover_stale_pending", new=AsyncMock()),
        patch(
            "app.main.scraper.ingest_all",
            new=AsyncMock(return_value=IngestResult(inserted=[], fetched=0)),
        ),
        patch("app.main.transformer.create_and_enqueue", new=AsyncMock()),
        patch("app.main.close_redis", new=AsyncMock()),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


async def test_lifespan_calls_ingest_all_after_migrations(app):
    from app.main import lifespan

    call_order: list[str] = []
    mock_cm, _ = _make_session_cm()
    mock_arq_pool = AsyncMock()

    async def mock_migrations() -> None:
        call_order.append("migrations")

    async def mock_recover(session, pool) -> int:
        call_order.append("recover")
        return 0

    async def mock_ingest(session) -> IngestResult:
        call_order.append("ingest_all")
        return IngestResult(inserted=[], fetched=0)

    async def mock_enqueue(session, pool, articles) -> None:
        call_order.append("create_and_enqueue")

    with (
        patch("app.main._run_migrations", side_effect=mock_migrations),
        patch(
            "app.main.arq_client.create_arq_pool",
            new=AsyncMock(return_value=mock_arq_pool),
        ),
        patch("app.main.arq_client.close_arq_pool", new=AsyncMock()),
        patch("app.main.AsyncSessionLocal", return_value=mock_cm),
        patch("app.main.transformer.recover_stale_pending", side_effect=mock_recover),
        patch("app.main.scraper.ingest_all", side_effect=mock_ingest),
        patch("app.main.transformer.create_and_enqueue", side_effect=mock_enqueue),
        patch("app.main.close_redis", new=AsyncMock()),
    ):
        async with lifespan(app):
            pass

    assert call_order == ["migrations", "recover", "ingest_all", "create_and_enqueue"]


async def test_post_scrape_happy_path_returns_202_with_inserted_and_fetched(
    scrape_client,
):
    article = Article(source=Source.NYT, title="T", url="http://x.com", description="D")
    result = IngestResult(
        inserted=[article, article],
        fetched=5,
        skipped_url_duplicates=1,
        skipped_near_duplicates=2,
        embedding_calls=3,
    )

    mock_enqueue = AsyncMock()
    with (
        patch(
            "app.routers.scrape.scraper.ingest_all",
            new=AsyncMock(return_value=result),
        ),
        patch("app.routers.scrape.transformer.create_and_enqueue", new=mock_enqueue),
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 202
    assert r.json() == {
        "inserted": 2,
        "fetched": 5,
        "skipped_url_duplicates": 1,
        "skipped_near_duplicates": 2,
        "embedding_calls": 3,
    }
    mock_enqueue.assert_awaited_once()


async def test_post_scrape_all_sources_failed_returns_503(scrape_client):
    with (
        patch(
            "app.routers.scrape.scraper.ingest_all",
            new=AsyncMock(
                side_effect=ServiceUnavailableError("All RSS sources failed")
            ),
        ),
        patch("app.routers.scrape.transformer.create_and_enqueue", new=AsyncMock()),
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 503
    assert r.json() == {"detail": "All RSS sources failed"}


async def test_post_scrape_second_call_returns_202_with_zero_inserted(scrape_client):
    result = IngestResult(inserted=[], fetched=8)

    with (
        patch(
            "app.routers.scrape.scraper.ingest_all",
            new=AsyncMock(return_value=result),
        ),
        patch("app.routers.scrape.transformer.create_and_enqueue", new=AsyncMock()),
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 202
    assert r.json() == {
        "inserted": 0,
        "fetched": 8,
        "skipped_url_duplicates": 0,
        "skipped_near_duplicates": 0,
        "embedding_calls": 0,
    }


async def test_post_scrape_awaits_create_and_enqueue_before_returning_response(
    scrape_client,
):
    article = Article(source=Source.NYT, title="T", url="http://x.com", description="D")
    call_order: list[str] = []

    async def mock_ingest(session) -> IngestResult:
        call_order.append("ingest_all")
        return IngestResult(inserted=[article], fetched=1)

    async def mock_enqueue(session, pool, articles) -> None:
        call_order.append("create_and_enqueue")

    with (
        patch("app.routers.scrape.scraper.ingest_all", side_effect=mock_ingest),
        patch(
            "app.routers.scrape.transformer.create_and_enqueue",
            side_effect=mock_enqueue,
        ),
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 202
    assert call_order == ["ingest_all", "create_and_enqueue"]
