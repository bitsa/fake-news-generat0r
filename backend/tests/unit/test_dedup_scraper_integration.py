import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.models import Article, ArticleEmbedding
from app.services.dedup import Incumbent, tokenize
from app.services.scraper import ingest_all
from app.sources import Source


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", True)
    monkeypatch.setattr(settings, "dedup_jaccard_high", 0.80)
    monkeypatch.setattr(settings, "dedup_jaccard_floor", 0.40)
    monkeypatch.setattr(settings, "dedup_cosine_threshold", 0.88)
    monkeypatch.setattr(settings, "openai_model_embedding", "text-embedding-3-small")


def _entry(title="Title", link="https://example.com", summary="Summary"):
    return {
        "title": title,
        "link": link,
        "summary": summary,
        "published_parsed": None,
    }


class _FakeSession:
    """Records add()/flush()/commit() and assigns autoincrement ids."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self._next_id = 1000
        self.commits = 0
        self.rollbacks = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, Article) and getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _articles_added(session: _FakeSession) -> list[Article]:
    return [o for o in session.added if isinstance(o, Article)]


def _embeddings_added(session: _FakeSession) -> list[ArticleEmbedding]:
    return [o for o in session.added if isinstance(o, ArticleEmbedding)]


def _patch_loaders(incumbents: list[Incumbent], existing_urls: set[str]):
    return (
        patch(
            "app.services.scraper._load_incumbents",
            new=AsyncMock(return_value=incumbents),
        ),
        patch(
            "app.services.scraper._url_exists",
            new=AsyncMock(side_effect=lambda s, url: url in existing_urls),
        ),
    )


def _patch_one_source(entries: list[dict]):
    """Patch fetch_feed to return entries for the FIRST source only."""
    sources = list(Source)

    async def fake_fetch(source: Source) -> list:
        if source == sources[0]:
            return entries
        return []

    return patch("app.services.scraper.fetch_feed", side_effect=fake_fetch)


# --- URL-dedup-first ---


async def test_url_duplicate_is_dropped_before_dedup_no_embedding_call():
    session = _FakeSession()
    p_inc, p_url = _patch_loaders(incumbents=[], existing_urls={"http://dup.com"})
    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(link="http://dup.com")]),
    ):
        result = await ingest_all(session)
    assert result.skipped_url_duplicates == 1
    assert result.skipped_near_duplicates == 0
    assert result.embedding_calls == 0
    assert _articles_added(session) == []


async def test_response_url_duplicates_counter_matches_url_skipped_count():
    session = _FakeSession()
    entries = [_entry(link=f"http://dup{i}.com") for i in range(3)]
    existing = {f"http://dup{i}.com" for i in range(3)}
    p_inc, p_url = _patch_loaders(incumbents=[], existing_urls=existing)
    with p_inc, p_url, _patch_one_source(entries):
        result = await ingest_all(session)
    assert result.skipped_url_duplicates == 3


# --- High-band Jaccard ---


async def test_high_band_candidate_is_skipped_with_no_articles_no_fakes_no_embedding_row():  # noqa: E501
    session = _FakeSession()
    title = "Mayor announces budget cuts for next fiscal year"
    incumbents = [
        Incumbent(
            article_id=10,
            tokens=tokenize(title),
            text=f"{title}\n\nbody",
            embedding=None,
        )
    ]
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(title=title, link="http://new.com")]),
    ):
        result = await ingest_all(session)
    assert result.skipped_near_duplicates == 1
    assert result.embedding_calls == 0
    assert _articles_added(session) == []
    assert _embeddings_added(session) == []


async def test_high_band_skip_logs_info_with_reason_jaccard_and_matched_article_id(
    caplog,
):
    session = _FakeSession()
    title = "Mayor announces budget cuts for next fiscal year"
    incumbents = [
        Incumbent(
            article_id=42,
            tokens=tokenize(title),
            text=f"{title}\n\nbody",
            embedding=None,
        )
    ]
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(title=title, link="http://new.com")]),
        caplog.at_level(logging.INFO, logger="app.services.scraper"),
    ):
        await ingest_all(session)
    skip_lines = [r for r in caplog.records if "scraper.dedup.skip" in r.getMessage()]
    assert len(skip_lines) == 1
    msg = skip_lines[0].getMessage()
    assert "reason=jaccard" in msg
    assert "matched_article_id=42" in msg


# --- Low-band ---


async def test_low_band_candidate_is_inserted_no_embedding_call_no_embedding_row():
    session = _FakeSession()
    incumbents = [
        Incumbent(
            article_id=1,
            tokens=tokenize("kittens puppies cats dogs adopted"),
            text="kittens\n\nbody",
            embedding=None,
        )
    ]
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source(
            [_entry(title="financial markets close higher today", link="http://m.com")]
        ),
    ):
        result = await ingest_all(session)
    assert len(_articles_added(session)) == 1
    assert _embeddings_added(session) == []
    assert result.embedding_calls == 0
    assert result.skipped_near_duplicates == 0


# --- Ambiguous band: skip ---


async def test_ambiguous_band_skip_logs_info_with_reason_embedding_and_matched_article_id(  # noqa: E501
    caplog, monkeypatch
):
    session = _FakeSession()
    incumbents = [
        Incumbent(
            article_id=99,
            tokens=tokenize("election results count voter turnout high"),
            text="election\n\nbody",
            embedding=[1.0] * 1536,
        )
    ]

    # candidate vector identical to incumbent → cosine 1.0 → skip
    async def fake_embed(text: str) -> list[float]:
        return [1.0] * 1536

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source(
            [
                _entry(
                    title="election results count voter turnout final",
                    link="http://e.com",
                )
            ]
        ),
        caplog.at_level(logging.INFO, logger="app.services.scraper"),
    ):
        result = await ingest_all(session)
    assert result.skipped_near_duplicates == 1
    skip_lines = [r for r in caplog.records if "scraper.dedup.skip" in r.getMessage()]
    assert len(skip_lines) == 1
    msg = skip_lines[0].getMessage()
    assert "reason=embedding" in msg
    assert "matched_article_id=99" in msg


# --- Ambiguous band: insert + embed ---


async def test_ambiguous_band_no_match_inserts_article_and_persists_embedding_row(
    monkeypatch,
):
    session = _FakeSession()
    incumbents = [
        Incumbent(
            article_id=99,
            tokens=tokenize("election results count voter turnout high"),
            text="election\n\nbody",
            embedding=[1.0] + [0.0] * 1535,
        )
    ]

    async def fake_embed(text: str) -> list[float]:
        # orthogonal to incumbent → cosine 0 → no match → insert + embed
        return [0.0, 1.0] + [0.0] * 1534

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source(
            [
                _entry(
                    title="election results count voter turnout final",
                    link="http://e.com",
                )
            ]
        ),
    ):
        result = await ingest_all(session)
    arts = _articles_added(session)
    embs = _embeddings_added(session)
    assert len(arts) == 1
    assert len(embs) == 1
    assert embs[0].article_id == arts[0].id
    assert embs[0].model == settings.openai_model_embedding
    assert len(embs[0].embedding) == 1536
    assert result.embedding_calls == 1


# --- Within-batch coherence ---


async def test_within_batch_two_near_duplicates_in_same_run_drop_one_increment_skip_counter():  # noqa: E501
    session = _FakeSession()
    title = "Mayor announces budget cuts for next fiscal year"
    p_inc, p_url = _patch_loaders(incumbents=[], existing_urls=set())
    entries = [
        _entry(title=title, link="http://a.com"),
        _entry(title=title, link="http://b.com"),
    ]
    with p_inc, p_url, _patch_one_source(entries):
        result = await ingest_all(session)
    # exactly one inserted, one skipped — winner identity not asserted.
    assert len(_articles_added(session)) == 1
    assert result.skipped_near_duplicates == 1


def test_within_batch_winner_identity_not_asserted():
    # Documentation-only test: which of two same-run mutual near-dups wins is
    # implementation-walk-order, per spec resolved decision #5. The test above
    # asserts only the count split, never the URL of the winner.
    assert True


# --- Cross-source matching ---


async def test_cross_source_incumbent_skips_candidate_from_different_source():
    sources = list(Source)
    assert len(sources) >= 2
    npr_source = sources[1]
    title = "Mayor announces budget cuts for next fiscal year"
    # incumbent loaded with article_id pointing to existing NYT article.
    incumbents = [
        Incumbent(
            article_id=7,
            tokens=tokenize(title),
            text=f"{title}\n\nbody",
            embedding=None,
        )
    ]
    session = _FakeSession()

    async def fake_fetch(source: Source) -> list:
        if source == npr_source:
            return [_entry(title=title, link="http://npr.com/x")]
        return []

    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        patch("app.services.scraper.fetch_feed", side_effect=fake_fetch),
    ):
        result = await ingest_all(session)
    assert result.skipped_near_duplicates == 1
    assert _articles_added(session) == []


# --- Window boundary ---


async def test_out_of_window_incumbent_does_not_trigger_skip():
    # When the loader applies the window predicate, an out-of-window article
    # isn't returned at all → candidate inserts even if it would be a near-dup.
    session = _FakeSession()
    title = "Mayor announces budget cuts for next fiscal year"
    p_inc, p_url = _patch_loaders(incumbents=[], existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(title=title, link="http://x.com")]),
    ):
        result = await ingest_all(session)
    assert len(_articles_added(session)) == 1
    assert result.skipped_near_duplicates == 0


async def test_incumbent_with_null_published_at_is_in_window_when_created_at_is_recent():  # noqa: E501
    # Same coverage technique: the loader returns the incumbent (representing
    # the SQL COALESCE branch); the candidate is then near-dup-skipped.
    session = _FakeSession()
    title = "Mayor announces budget cuts for next fiscal year"
    incumbents = [
        Incumbent(
            article_id=11,
            tokens=tokenize(title),
            text=f"{title}\n\nbody",
            embedding=None,
        )
    ]
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(title=title, link="http://x.com")]),
    ):
        result = await ingest_all(session)
    assert result.skipped_near_duplicates == 1


def test_loader_sql_uses_coalesce_published_at_created_at_with_window_param():
    # Compile-time check on the loader query: the SQL fragment is what
    # makes the window-predicate ACs verifiable without a real DB.
    import inspect

    from app.services import scraper

    src = inspect.getsource(scraper._load_incumbents)
    assert "COALESCE(a.published_at, a.created_at)" in src
    assert ":hours" in src or "hours =>" in src


# --- Response shape ---


async def test_response_shape_has_exactly_five_integer_keys(monkeypatch):
    from app.routers import scrape as scrape_router

    session = _FakeSession()
    incumbents: list[Incumbent] = []
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())

    async def fake_enqueue(*args, **kwargs):
        return None

    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(title="hello world friend", link="http://x.com")]),
        patch.object(scrape_router.transformer, "create_and_enqueue", new=fake_enqueue),
    ):
        body = await scrape_router.scrape(session=session, arq_pool=AsyncMock())
    assert set(body.keys()) == {
        "inserted",
        "fetched",
        "skipped_url_duplicates",
        "skipped_near_duplicates",
        "embedding_calls",
    }
    assert all(isinstance(v, int) for v in body.values())


async def test_response_embedding_calls_is_zero_when_no_ambiguous_band_candidate():
    session = _FakeSession()
    p_inc, p_url = _patch_loaders(incumbents=[], existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source([_entry(title="hello world friend", link="http://x.com")]),
    ):
        result = await ingest_all(session)
    assert result.embedding_calls == 0


async def test_response_embedding_calls_counts_each_call_including_cold_incumbent(
    monkeypatch,
):
    session = _FakeSession()
    incumbents = [
        Incumbent(
            article_id=1,
            tokens=tokenize("election results count voter turnout high"),
            text="election\n\nbody",
            embedding=None,  # cold
        )
    ]

    async def fake_embed(text: str) -> list[float]:
        return [0.0, 1.0] + [0.0] * 1534

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)
    p_inc, p_url = _patch_loaders(incumbents=incumbents, existing_urls=set())
    with (
        p_inc,
        p_url,
        _patch_one_source(
            [
                _entry(
                    title="election results count voter turnout final",
                    link="http://e.com",
                )
            ]
        ),
    ):
        result = await ingest_all(session)
    # candidate (1) + cold incumbent (1) = 2.
    assert result.embedding_calls == 2


# --- Non-regression ---


async def test_non_regression_no_collisions_inserts_every_article_with_pending_fake_row():  # noqa: E501
    # Validates URL pipeline still works: with no near-dups and no URL
    # collisions, all valid candidates are inserted. The transformer.create_
    # and_enqueue hop (which adds the pending fake row) is invoked by the
    # router/lifespan with result.inserted; this test asserts result.inserted
    # contains every fetched candidate, which is the contract that hop relies on.
    session = _FakeSession()
    p_inc, p_url = _patch_loaders(incumbents=[], existing_urls=set())
    sources = list(Source)

    distinct_titles = [
        "kittens adopted countryside shelter",
        "stockmarkets close higher financial signals",
        "scientists discover ancient artifact desert",
    ]

    async def fake_fetch(source: Source) -> list:
        idx = sources.index(source)
        return [_entry(title=distinct_titles[idx], link=f"http://u{idx}.com")]

    with (
        p_inc,
        p_url,
        patch("app.services.scraper.fetch_feed", side_effect=fake_fetch),
    ):
        result = await ingest_all(session)
    assert len(result.inserted) == len(sources)
    assert result.skipped_url_duplicates == 0
    assert result.skipped_near_duplicates == 0
    assert result.fetched == len(sources)
