from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.models import Article, ArticleFake
from app.services.articles import get_articles
from app.sources import Source


def _article(*, id: int, published_at: datetime | None) -> Article:
    return Article(
        id=id,
        source=Source.NYT,
        title=f"title-{id}",
        description="desc",
        url=f"http://example.com/{id}",
        published_at=published_at,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )


def _fake(*, article_id: int) -> ArticleFake:
    return ArticleFake(
        article_id=article_id,
        transform_status="completed",
        title=f"fake-{article_id}",
        description="fake desc",
        model="gpt-test",
        temperature=0.7,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )


def _make_session(*, total: int, pending: int, rows: list) -> AsyncMock:
    session = AsyncMock()
    session.scalar.side_effect = [total, pending]
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    session.execute.return_value = mock_result
    return session


async def test_get_articles_service_ordering_later_published_at_appears_first():
    earlier = _article(id=1, published_at=datetime(2026, 4, 1, tzinfo=UTC))
    later = _article(id=2, published_at=datetime(2026, 5, 1, tzinfo=UTC))
    # Service trusts SQL ORDER BY — caller returns rows in DB-sorted order.
    rows = [(later, _fake(article_id=2)), (earlier, _fake(article_id=1))]
    session = _make_session(total=2, pending=0, rows=rows)

    response = await get_articles(session)

    assert [p.id for p in response.articles] == [2, 1]


async def test_get_articles_service_null_published_at_appears_after_dated_articles():
    dated = _article(id=1, published_at=datetime(2026, 4, 1, tzinfo=UTC))
    undated = _article(id=2, published_at=None)
    rows = [(dated, _fake(article_id=1)), (undated, _fake(article_id=2))]
    session = _make_session(total=2, pending=0, rows=rows)

    response = await get_articles(session)

    assert [p.id for p in response.articles] == [1, 2]
    assert response.articles[1].article.published_at is None


async def test_get_articles_service_fake_id_equals_article_id():
    article = _article(id=99, published_at=datetime(2026, 5, 1, tzinfo=UTC))
    fake = _fake(article_id=99)
    session = _make_session(total=1, pending=0, rows=[(article, fake)])

    response = await get_articles(session)

    pair = response.articles[0]
    assert pair.id == 99
    assert pair.article.id == 99
    assert pair.fake.id == 99
