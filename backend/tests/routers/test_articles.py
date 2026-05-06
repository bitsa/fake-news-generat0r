from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.arq_client import get_arq_pool
from app.db import get_session
from app.schemas.articles import (
    ArticleOut,
    ArticlePairOut,
    ArticlesResponse,
    FakeOut,
)
from app.services.scraper import IngestResult


def _make_session_cm() -> tuple[MagicMock, AsyncMock]:
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_session


@pytest_asyncio.fixture
async def articles_client(app):
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


def _pair(
    *,
    id: int,
    title: str = "T",
    description: str | None = "D",
    url: str | None = None,
    source: str = "NYT",
    published_at: datetime | None = None,
    fake_title: str | None = "F-T",
    fake_description: str | None = "F-D",
    model: str | None = "gpt-test",
    temperature: float | None = 0.7,
) -> ArticlePairOut:
    created = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    return ArticlePairOut(
        id=id,
        article=ArticleOut(
            id=id,
            source=source,
            title=title,
            description=description,
            url=url or f"http://example.com/{id}",
            published_at=published_at,
            created_at=created,
        ),
        fake=FakeOut.model_validate(
            {
                "article_id": id,
                "title": fake_title,
                "description": fake_description,
                "model": model,
                "temperature": temperature,
                "created_at": created,
            }
        ),
    )


async def test_get_articles_happy_path_completed_pair_returns_200(articles_client):
    response = ArticlesResponse(total=1, pending=0, articles=[_pair(id=1)])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["pending"] == 0
    assert len(body["articles"]) == 1


async def test_get_articles_pending_fake_excluded_from_articles_counted_in_pending(
    articles_client,
):
    response = ArticlesResponse(total=1, pending=1, articles=[])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    body = r.json()
    assert body["pending"] == 1
    assert body["articles"] == []


async def test_get_articles_no_fake_article_excluded_from_articles_and_not_in_pending(
    articles_client,
):
    response = ArticlesResponse(total=1, pending=0, articles=[])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    body = r.json()
    assert body["total"] == 1
    assert body["pending"] == 0
    assert body["articles"] == []


async def test_get_articles_total_counts_all_articles_regardless_of_fake_status(
    articles_client,
):
    response = ArticlesResponse(total=3, pending=1, articles=[_pair(id=1)])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    assert r.json()["total"] == 3


async def test_get_articles_pending_counts_only_pending_fakes(articles_client):
    response = ArticlesResponse(total=2, pending=1, articles=[_pair(id=1)])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    body = r.json()
    assert body["pending"] == 1
    assert len(body["articles"]) == 1


async def test_get_articles_empty_db_returns_200_with_zeros_and_empty_array(
    articles_client,
):
    response = ArticlesResponse(total=0, pending=0, articles=[])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    assert r.status_code == 200
    assert r.json() == {"total": 0, "pending": 0, "articles": []}


async def test_get_articles_response_shape_has_exactly_three_top_level_keys(
    articles_client,
):
    response = ArticlesResponse(total=0, pending=0, articles=[])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    body = r.json()
    assert set(body.keys()) == {"total", "pending", "articles"}


async def test_get_articles_each_pair_has_id_article_and_fake_with_all_required_fields(
    articles_client,
):
    response = ArticlesResponse(total=1, pending=0, articles=[_pair(id=42)])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    pair = r.json()["articles"][0]
    assert set(pair.keys()) == {"id", "article", "fake"}
    assert set(pair["article"].keys()) == {
        "id",
        "source",
        "title",
        "description",
        "url",
        "published_at",
        "created_at",
    }
    assert set(pair["fake"].keys()) == {
        "id",
        "title",
        "description",
        "model",
        "temperature",
        "created_at",
    }
    assert pair["id"] == 42
    assert pair["article"]["id"] == 42
    assert pair["fake"]["id"] == 42


async def test_get_articles_nullable_fields_may_be_null_in_both_article_and_fake(
    articles_client,
):
    response = ArticlesResponse(
        total=1,
        pending=0,
        articles=[
            _pair(
                id=1,
                description=None,
                published_at=None,
                fake_title=None,
                fake_description=None,
                model=None,
                temperature=None,
            )
        ],
    )
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    pair = r.json()["articles"][0]
    assert pair["article"]["description"] is None
    assert pair["article"]["published_at"] is None
    assert pair["fake"]["title"] is None
    assert pair["fake"]["description"] is None
    assert pair["fake"]["model"] is None
    assert pair["fake"]["temperature"] is None
    assert pair["fake"]["created_at"] is not None


async def test_get_articles_source_field_serialised_as_string_value_not_enum_index(
    articles_client,
):
    response = ArticlesResponse(
        total=3,
        pending=0,
        articles=[
            _pair(id=1, source="NYT"),
            _pair(id=2, source="NPR"),
            _pair(id=3, source="Guardian"),
        ],
    )
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    sources = [p["article"]["source"] for p in r.json()["articles"]]
    assert sources == ["NYT", "NPR", "Guardian"]


async def test_get_articles_datetime_fields_serialised_as_iso8601_with_timezone(
    articles_client,
):
    pub = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
    response = ArticlesResponse(
        total=1, pending=0, articles=[_pair(id=1, published_at=pub)]
    )
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    pair = r.json()["articles"][0]
    for value in (
        pair["article"]["published_at"],
        pair["article"]["created_at"],
        pair["fake"]["created_at"],
    ):
        assert isinstance(value, str)
        assert value.endswith("+00:00") or value.endswith("Z")


async def test_get_articles_no_auth_required_returns_200(articles_client):
    response = ArticlesResponse(total=0, pending=0, articles=[])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        r = await articles_client.get("/api/articles")

    assert r.status_code == 200
    assert "WWW-Authenticate" not in r.headers


async def test_get_articles_registered_under_api_prefix(articles_client):
    response = ArticlesResponse(total=0, pending=0, articles=[])
    with patch(
        "app.routers.articles.articles_service.get_articles",
        new=AsyncMock(return_value=response),
    ):
        ok = await articles_client.get("/api/articles")
        unprefixed = await articles_client.get("/articles")

    assert ok.status_code == 200
    assert unprefixed.status_code == 404
