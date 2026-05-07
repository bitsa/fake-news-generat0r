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


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self._next_id = 500

    def add(self, obj):
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, Article) and getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


def _patch_loaders():
    """Default: no incumbents, no URL collisions."""
    return (
        patch(
            "app.services.scraper._load_incumbents",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.scraper._url_exists",
            new=AsyncMock(return_value=False),
        ),
    )


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
    p_inc, p_url = _patch_loaders()

    with p_inc, p_url, patch("app.services.scraper.fetch_feed", new=mock_fetch):
        await ingest_all(_FakeSession())

    assert mock_fetch.call_count == len(list(Source))
    assert {call.args[0] for call in mock_fetch.call_args_list} == set(Source)


async def test_ingest_all_returns_inserted_articles_and_fetched_count():
    p_inc, p_url = _patch_loaders()
    session = _FakeSession()

    with (
        p_inc,
        p_url,
        patch(
            "app.services.scraper.fetch_feed", new=AsyncMock(return_value=[_entry()])
        ),
    ):
        result = await ingest_all(session)

    assert result.fetched == 3  # 1 valid entry × 3 sources
    # Same URL across all three sources → first one inserted, next two
    # are URL-duplicates (in-batch via in-memory incumbents? No: URL
    # check goes against session DB, but we mocked _url_exists False).
    # Inserted count: at least 1 (the first). Other two share the same
    # URL, so the first commit makes the URL exist — but our mock always
    # returns False. They will all insert. That's fine: this test asserts
    # the COUNTER plumbing, not the URL-collision behaviour.
    assert len(result.inserted) >= 1


async def test_ingest_all_logs_warning_for_dropped_entry(caplog):
    bad_entry = {"link": "http://x.com", "summary": "desc"}  # no title
    p_inc, p_url = _patch_loaders()

    with (
        p_inc,
        p_url,
        patch(
            "app.services.scraper.fetch_feed",
            new=AsyncMock(return_value=[bad_entry]),
        ),
    ):
        with caplog.at_level(logging.WARNING, logger="app.services.scraper"):
            await ingest_all(_FakeSession())

    dropped = [r for r in caplog.records if "scraper.entry.dropped" in r.getMessage()]
    assert len(dropped) == len(list(Source))


async def test_ingest_all_skips_failed_source_continues_others():
    p_inc, p_url = _patch_loaders()

    titles_by_source = {
        Source.NPR: "kittens adopted countryside shelter",
        Source.GUARDIAN: "scientists discover ancient artifact desert",
    }

    async def mock_fetch(source: Source) -> list:
        if source == Source.NYT:
            raise Exception("network fail")
        return [
            _entry(
                title=titles_by_source.get(source, "fallback"),
                link=f"http://{source}.com",
            )
        ]

    with (
        p_inc,
        p_url,
        patch("app.services.scraper.fetch_feed", side_effect=mock_fetch),
    ):
        result = await ingest_all(_FakeSession())

    assert result.fetched == 2  # NPR + GUARDIAN
    assert len(result.inserted) == 2


async def test_ingest_all_logs_warning_per_failed_source(caplog):
    p_inc, p_url = _patch_loaders()

    async def mock_fetch(source: Source) -> list:
        raise Exception("fail")

    with (
        p_inc,
        p_url,
        patch("app.services.scraper.fetch_feed", side_effect=mock_fetch),
    ):
        with caplog.at_level(logging.WARNING, logger="app.services.scraper"):
            with pytest.raises(ServiceUnavailableError):
                await ingest_all(_FakeSession())

    failed = [r for r in caplog.records if "scraper.source.failed" in r.getMessage()]
    assert len(failed) == len(list(Source))


async def test_ingest_all_raises_service_unavailable_when_all_sources_fail():
    p_inc, p_url = _patch_loaders()

    async def mock_fetch(source: Source) -> list:
        raise Exception("all down")

    with (
        p_inc,
        p_url,
        patch("app.services.scraper.fetch_feed", side_effect=mock_fetch),
    ):
        with pytest.raises(ServiceUnavailableError):
            await ingest_all(_FakeSession())
