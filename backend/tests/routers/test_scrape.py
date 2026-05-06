from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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

    async def override_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_session] = override_get_session

    with (
        patch("app.main._run_migrations", new=AsyncMock()),
        patch("app.main.AsyncSessionLocal", return_value=mock_cm),
        patch(
            "app.main.scraper.ingest_all",
            new=AsyncMock(return_value=IngestResult(inserted=[], fetched=0)),
        ),
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

    async def mock_migrations() -> None:
        call_order.append("migrations")

    async def mock_ingest(session) -> IngestResult:
        call_order.append("ingest_all")
        return IngestResult(inserted=[], fetched=0)

    with (
        patch("app.main._run_migrations", side_effect=mock_migrations),
        patch("app.main.AsyncSessionLocal", return_value=mock_cm),
        patch("app.main.scraper.ingest_all", side_effect=mock_ingest),
        patch("app.main.close_redis", new=AsyncMock()),
    ):
        async with lifespan(app):
            pass

    assert call_order == ["migrations", "ingest_all"]


async def test_post_scrape_happy_path_returns_202_with_inserted_and_fetched(
    scrape_client,
):
    article = Article(source=Source.NYT, title="T", url="http://x.com", description="D")
    result = IngestResult(inserted=[article, article], fetched=5)

    with patch(
        "app.routers.scrape.scraper.ingest_all", new=AsyncMock(return_value=result)
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 202
    assert r.json() == {"inserted": 2, "fetched": 5}


async def test_post_scrape_all_sources_failed_returns_503(scrape_client):
    with patch(
        "app.routers.scrape.scraper.ingest_all",
        new=AsyncMock(side_effect=ServiceUnavailableError("All RSS sources failed")),
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 503
    assert r.json() == {"detail": "All RSS sources failed"}


async def test_post_scrape_second_call_returns_202_with_zero_inserted(scrape_client):
    result = IngestResult(inserted=[], fetched=8)

    with patch(
        "app.routers.scrape.scraper.ingest_all", new=AsyncMock(return_value=result)
    ):
        r = await scrape_client.post("/api/scrape")

    assert r.status_code == 202
    assert r.json() == {"inserted": 0, "fetched": 8}
