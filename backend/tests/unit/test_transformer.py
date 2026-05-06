import logging
from unittest.mock import AsyncMock, MagicMock

from app.services.transformer import create_and_enqueue, recover_stale_pending


def _make_session(scalars_return=None):
    """Return a mock AsyncSession; execute().scalars().all() yields scalars_return."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = scalars_return or []
    session = AsyncMock()
    session.execute.return_value = mock_result
    return session


def _make_article(article_id: int):
    article = MagicMock()
    article.id = article_id
    return article


# ---------------------------------------------------------------------------
# create_and_enqueue
# ---------------------------------------------------------------------------


async def test_create_and_enqueue_inserts_pending_fake_for_each_new_article():
    session = AsyncMock()
    arq_pool = AsyncMock()
    articles = [_make_article(1), _make_article(2)]

    await create_and_enqueue(session, arq_pool, articles)

    assert session.add_all.call_count == 1
    added = session.add_all.call_args[0][0]
    assert len(added) == 2
    assert {f.article_id for f in added} == {1, 2}


async def test_create_and_enqueue_commits_session_after_inserting_fakes():
    session = AsyncMock()
    arq_pool = AsyncMock()
    articles = [_make_article(10)]

    await create_and_enqueue(session, arq_pool, articles)

    session.commit.assert_awaited_once()


async def test_create_and_enqueue_does_nothing_when_articles_list_is_empty():
    session = AsyncMock()
    arq_pool = AsyncMock()

    await create_and_enqueue(session, arq_pool, [])

    session.add_all.assert_not_called()
    session.commit.assert_not_called()
    arq_pool.enqueue_job.assert_not_called()


async def test_create_and_enqueue_failed_enqueue_does_not_abort_remaining_articles():
    session = AsyncMock()
    arq_pool = AsyncMock()
    arq_pool.enqueue_job.side_effect = [Exception("redis down"), None, None]
    articles = [_make_article(1), _make_article(2), _make_article(3)]

    await create_and_enqueue(session, arq_pool, articles)

    assert arq_pool.enqueue_job.call_count == 3
    arq_pool.enqueue_job.assert_any_call("transform_article", 2)
    arq_pool.enqueue_job.assert_any_call("transform_article", 3)


async def test_create_and_enqueue_failed_enqueue_emits_warning_log(caplog):
    session = AsyncMock()
    arq_pool = AsyncMock()
    arq_pool.enqueue_job.side_effect = Exception("boom")
    articles = [_make_article(99)]

    with caplog.at_level(logging.WARNING, logger="app.services.transformer"):
        await create_and_enqueue(session, arq_pool, articles)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    assert "99" in warning_records[0].message


# ---------------------------------------------------------------------------
# recover_stale_pending
# ---------------------------------------------------------------------------


async def test_recover_stale_pending_enqueues_rows_older_than_5_minutes():
    session = _make_session(scalars_return=[10, 20])
    arq_pool = AsyncMock()

    count = await recover_stale_pending(session, arq_pool)

    assert count == 2
    arq_pool.enqueue_job.assert_any_call("transform_article", 10)
    arq_pool.enqueue_job.assert_any_call("transform_article", 20)


async def test_recover_stale_pending_skips_rows_created_within_5_minutes():
    # Query returns no rows (representing recent rows were filtered by WHERE)
    session = _make_session(scalars_return=[])
    arq_pool = AsyncMock()

    count = await recover_stale_pending(session, arq_pool)

    assert count == 0
    arq_pool.enqueue_job.assert_not_called()


async def test_recover_stale_pending_skips_completed_rows():
    # Query returns no rows (representing completed rows were filtered by WHERE)
    session = _make_session(scalars_return=[])
    arq_pool = AsyncMock()

    count = await recover_stale_pending(session, arq_pool)

    assert count == 0
    arq_pool.enqueue_job.assert_not_called()
