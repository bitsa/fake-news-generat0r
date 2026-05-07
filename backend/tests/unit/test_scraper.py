import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import ServiceUnavailableError
from app.models import Article
from app.services.scraper import fetch_feed, ingest_all, parse_entry
from app.sources import Source


def _entry(
    title="Title",
    link="https://example.com",
    summary="Summary",
    published_parsed=None,
):
    return {
        "title": title,
        "link": link,
        "summary": summary,
        "published_parsed": published_parsed,
    }


def _mock_http_client(response_text="<rss/>"):
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_response


def _mock_session(returned_articles: list[Article] | None = None) -> AsyncMock:
    session = AsyncMock()
    if returned_articles is not None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = returned_articles
        session.execute = AsyncMock(return_value=mock_result)
    return session


# --- fetch_feed ---


async def test_fetch_feed_passes_response_text_to_feedparser():
    mock_client, mock_response = _mock_http_client("<rss>content</rss>")
    mock_feed = MagicMock()
    mock_feed.entries = []

    with (
        patch("app.services.scraper.httpx.AsyncClient", return_value=mock_client),
        patch(
            "app.services.scraper.feedparser.parse", return_value=mock_feed
        ) as mock_parse,
    ):
        await fetch_feed(Source.NYT)

    mock_parse.assert_called_once_with(mock_response.text)


async def test_fetch_feed_caps_at_scrape_max_per_source():
    mock_client, _ = _mock_http_client()
    mock_feed = MagicMock()
    mock_feed.entries = [MagicMock() for _ in range(20)]

    with (
        patch("app.services.scraper.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.scraper.feedparser.parse", return_value=mock_feed),
        patch("app.services.scraper.settings") as mock_settings,
    ):
        mock_settings.scrape_max_per_source = 3
        result = await fetch_feed(Source.NPR)

    assert len(result) == 3


# --- parse_entry ---


def test_parse_entry_returns_article_for_valid_entry():
    entry = _entry(published_parsed=(2024, 1, 15, 12, 0, 0, 0, 0, 0))
    result = parse_entry(entry, Source.NYT)
    assert result is not None
    assert result.source == Source.NYT
    assert result.title == "Title"
    assert result.url == "https://example.com"
    assert result.description == "Summary"
    assert result.published_at == datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)


def test_parse_entry_returns_none_for_missing_title():
    assert parse_entry({"link": "https://x.com", "summary": "D"}, Source.NYT) is None


def test_parse_entry_returns_none_for_missing_url():
    assert parse_entry({"title": "T", "summary": "D"}, Source.NYT) is None


def test_parse_entry_returns_none_for_missing_description():
    assert parse_entry({"title": "T", "link": "https://x.com"}, Source.NYT) is None


def test_parse_entry_returns_none_for_blank_title():
    assert parse_entry(_entry(title="   "), Source.NYT) is None


def test_parse_entry_returns_none_for_blank_url():
    assert parse_entry(_entry(link="   "), Source.NYT) is None


def test_parse_entry_returns_none_for_blank_description():
    assert parse_entry(_entry(summary="   "), Source.NYT) is None


def test_parse_entry_cleans_html_in_title_and_description():
    entry = _entry(
        title="Apples &amp; <b>oranges</b>",
        summary="<p>hello world</p>",
    )
    result = parse_entry(entry, Source.NYT)
    assert result is not None
    assert "<" not in result.title
    assert "&amp;" not in result.title
    assert "<" not in result.description
    assert "Apples" in result.title
    assert "oranges" in result.title
    assert "hello" in result.description
    assert "world" in result.description


def test_parse_entry_returns_none_for_tag_only_summary():
    assert parse_entry(_entry(summary="<p></p>"), Source.NYT) is None


def test_parse_entry_returns_none_for_tag_only_title():
    assert parse_entry(_entry(title="<br/><br/>"), Source.NYT) is None


def test_parse_entry_preserves_url_query_and_fragment():
    url = "https://example.com/path?a=1&b=2#frag"
    result = parse_entry(_entry(link=url), Source.NYT)
    assert result is not None
    assert result.url == url


# --- ingest_all ---


async def test_ingest_all_fetches_all_three_sources():
    mock_fetch = AsyncMock(return_value=[])

    with patch("app.services.scraper.fetch_feed", new=mock_fetch):
        await ingest_all(AsyncMock())

    assert mock_fetch.call_count == len(list(Source))
    assert {call.args[0] for call in mock_fetch.call_args_list} == set(Source)


async def test_ingest_all_commits_after_each_source():
    session = AsyncMock()

    with patch("app.services.scraper.fetch_feed", new=AsyncMock(return_value=[])):
        await ingest_all(session)

    assert session.commit.call_count == len(list(Source))


async def test_ingest_all_returns_inserted_articles_and_fetched_count():
    article = Article(
        source=Source.NYT, title="T", url="http://nyt.com", description="D"
    )
    session = _mock_session([article])

    with patch(
        "app.services.scraper.fetch_feed", new=AsyncMock(return_value=[_entry()])
    ):
        result = await ingest_all(session)

    assert result.fetched == 3  # 1 valid entry × 3 sources
    assert len(result.inserted) == 3
    assert result.inserted[0] is article


async def test_ingest_all_uses_on_conflict_do_nothing():
    article = Article(
        source=Source.NYT,
        title="Title",
        url="https://example.com",
        description="Summary",
    )

    first_result = MagicMock()
    first_result.scalars.return_value.all.return_value = [article]
    session1 = AsyncMock()
    session1.execute = AsyncMock(return_value=first_result)

    second_result = MagicMock()
    second_result.scalars.return_value.all.return_value = []
    session2 = AsyncMock()
    session2.execute = AsyncMock(return_value=second_result)

    with patch(
        "app.services.scraper.fetch_feed", new=AsyncMock(return_value=[_entry()])
    ):
        r1 = await ingest_all(session1)
        r2 = await ingest_all(session2)

    assert len(r1.inserted) > 0
    assert len(r2.inserted) == 0


async def test_ingest_all_logs_warning_for_dropped_entry(caplog):
    bad_entry = {"link": "http://x.com", "summary": "desc"}  # no title

    with patch(
        "app.services.scraper.fetch_feed",
        new=AsyncMock(return_value=[bad_entry]),
    ):
        with caplog.at_level(logging.WARNING, logger="app.services.scraper"):
            await ingest_all(AsyncMock())

    dropped = [r for r in caplog.records if "scraper.entry.dropped" in r.getMessage()]
    assert len(dropped) == len(list(Source))


async def test_ingest_all_skips_failed_source_continues_others():
    article = Article(
        source=Source.NPR, title="T", url="http://npr.com", description="D"
    )
    session = _mock_session([article])

    async def mock_fetch(source: Source) -> list:
        if source == Source.NYT:
            raise Exception("network fail")
        return [_entry(link=f"http://{source}.com")]

    with patch("app.services.scraper.fetch_feed", side_effect=mock_fetch):
        result = await ingest_all(session)

    assert result.fetched == 2  # NPR + GUARDIAN
    assert len(result.inserted) == 2


async def test_ingest_all_logs_warning_per_failed_source(caplog):
    async def mock_fetch(source: Source) -> list:
        raise Exception("fail")

    with patch("app.services.scraper.fetch_feed", side_effect=mock_fetch):
        with caplog.at_level(logging.WARNING, logger="app.services.scraper"):
            with pytest.raises(ServiceUnavailableError):
                await ingest_all(AsyncMock())

    failed = [r for r in caplog.records if "scraper.source.failed" in r.getMessage()]
    assert len(failed) == len(list(Source))


async def test_ingest_all_raises_service_unavailable_when_all_sources_fail():
    async def mock_fetch(source: Source) -> list:
        raise Exception("all down")

    with patch("app.services.scraper.fetch_feed", side_effect=mock_fetch):
        with pytest.raises(ServiceUnavailableError):
            await ingest_all(AsyncMock())
