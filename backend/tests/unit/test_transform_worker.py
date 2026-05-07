import logging
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.services.openai_transform import (
    MOCK_DESCRIPTION,
    MOCK_TITLE,
    SatiricalPair,
)
from app.workers.transform import WorkerSettings, transform_article


def _make_session_cm(get_returns=None):
    """Build an AsyncSessionLocal mock whose session.get() pops from a list.

    ``get_returns`` is consumed in call order — first call returns the
    ArticleFake, second call returns the Article.
    """
    if get_returns is None:
        get_returns = []
    mock_session = AsyncMock()

    async def _get(model_cls, pk):
        if get_returns:
            return get_returns.pop(0)
        return None

    mock_session.get = AsyncMock(side_effect=_get)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_local = MagicMock(return_value=mock_cm)
    return mock_local, mock_session


def _make_fake(article_id: int = 1, status: str = "pending"):
    fake = MagicMock()
    fake.article_id = article_id
    fake.transform_status = status
    return fake


def _make_article(article_id: int = 1, title: str = "OT", description: str = "OD"):
    article = MagicMock()
    article.id = article_id
    article.title = title
    article.description = description
    return article


def _patch_service(return_pair=None, side_effect=None):
    if side_effect is not None:
        return patch(
            "app.workers.transform.openai_transform.generate_satirical",
            new=AsyncMock(side_effect=side_effect),
        )
    return patch(
        "app.workers.transform.openai_transform.generate_satirical",
        new=AsyncMock(
            return_value=return_pair
            or SatiricalPair(title=MOCK_TITLE, description=MOCK_DESCRIPTION)
        ),
    )


# ---------------------------------------------------------------------------
# Happy path — service produces pair, worker writes it to row
# ---------------------------------------------------------------------------


async def test_transform_article_sets_completed_status_and_fills_mock_content():
    fake = _make_fake(1)
    article = _make_article(1, "OT", "OD")
    mock_local, mock_session = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
    ):
        await transform_article({}, article_id=1)

    assert fake.title == MOCK_TITLE
    assert fake.description == MOCK_DESCRIPTION
    assert fake.transform_status == "completed"
    mock_session.commit.assert_awaited_once()


async def test_transform_article_completed_row_model_equals_settings_openai_model_transform():  # noqa: E501
    fake = _make_fake(1)
    article = _make_article(1)
    mock_local, _ = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
    ):
        await transform_article({}, article_id=1)

    assert fake.model == settings.openai_model_transform


async def test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform():  # noqa: E501
    fake = _make_fake(1)
    article = _make_article(1)
    mock_local, _ = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
    ):
        await transform_article({}, article_id=1)

    assert fake.temperature == settings.openai_temperature_transform


async def test_transform_article_passes_original_article_title_and_description_to_service():  # noqa: E501
    fake = _make_fake(1)
    article = _make_article(1, title="Original headline", description="Original body")
    mock_local, _ = _make_session_cm(get_returns=[fake, article])
    service = AsyncMock(return_value=SatiricalPair(title="t", description="d"))

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        patch("app.workers.transform.openai_transform.generate_satirical", new=service),
    ):
        await transform_article({}, article_id=1)

    service.assert_awaited_once_with("Original headline", "Original body")


async def test_transform_article_writes_service_response_to_fake_row():
    fake = _make_fake(1)
    article = _make_article(1)
    mock_local, _ = _make_session_cm(get_returns=[fake, article])
    pair = SatiricalPair(title="Service title", description="Service desc")

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(return_pair=pair),
    ):
        await transform_article({}, article_id=1)

    assert fake.title == "Service title"
    assert fake.description == "Service desc"


# ---------------------------------------------------------------------------
# Idempotency — completed row is a no-op
# ---------------------------------------------------------------------------


async def test_transform_article_completed_row_skips_openai_call():
    fake = _make_fake(1, status="completed")
    mock_local, _ = _make_session_cm(get_returns=[fake])
    service = AsyncMock()

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        patch("app.workers.transform.openai_transform.generate_satirical", new=service),
    ):
        await transform_article({}, article_id=1)

    service.assert_not_called()


async def test_transform_article_completed_row_does_not_modify_row():
    fake = _make_fake(1, status="completed")
    fake.title = "preexisting title"
    fake.description = "preexisting description"
    mock_local, mock_session = _make_session_cm(get_returns=[fake])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
    ):
        await transform_article({}, article_id=1)

    assert fake.title == "preexisting title"
    assert fake.description == "preexisting description"
    mock_session.commit.assert_not_called()


async def test_transform_article_completed_row_logs_skip_event(caplog):
    fake = _make_fake(1, status="completed")
    mock_local, _ = _make_session_cm(get_returns=[fake])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
        caplog.at_level(logging.INFO, logger="app.workers.transform"),
    ):
        await transform_article({}, article_id=1)

    skip_records = [r for r in caplog.records if "skip.completed" in r.getMessage()]
    assert len(skip_records) == 1
    assert "1" in skip_records[0].getMessage()


# ---------------------------------------------------------------------------
# Non-existent fake row
# ---------------------------------------------------------------------------


async def test_transform_article_skips_nonexistent_article_id_without_raising():
    mock_local, mock_session = _make_session_cm(get_returns=[None])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
    ):
        await transform_article({}, article_id=999)

    mock_session.commit.assert_not_called()


async def test_transform_article_skips_nonexistent_article_id_logs_skip_event(caplog):
    mock_local, _ = _make_session_cm(get_returns=[None])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(),
        caplog.at_level(logging.INFO, logger="app.workers.transform"),
    ):
        await transform_article({}, article_id=42)

    skip_records = [r for r in caplog.records if "skip" in r.getMessage()]
    assert len(skip_records) == 1
    assert "42" in skip_records[0].getMessage()


# ---------------------------------------------------------------------------
# Exception path — service raises, parent article deleted (cascade clears fake);
# next scrape will re-insert (no URL conflict) and re-enqueue a fresh pending row.
# ---------------------------------------------------------------------------


async def test_transform_article_deletes_article_row_on_unexpected_exception():
    fake = _make_fake(7)
    article = _make_article(7)
    mock_local, mock_session = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(side_effect=Exception("openai flake")),
    ):
        await transform_article({}, article_id=7)

    mock_session.rollback.assert_awaited_once()
    assert mock_session.execute.await_count == 1
    mock_session.commit.assert_awaited_once()


async def test_transform_article_failure_targets_articles_table_not_fakes():
    from app.models import Article

    fake = _make_fake(8)
    article = _make_article(8)
    mock_local, mock_session = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(side_effect=Exception("flake")),
    ):
        await transform_article({}, article_id=8)

    assert mock_session.execute.await_count == 1
    stmt = mock_session.execute.await_args.args[0]
    assert stmt.table.name == Article.__tablename__
    compiled = stmt.compile(compile_kwargs={"literal_binds": True})
    sql = str(compiled).lower()
    assert " where " in sql
    assert f"{Article.__tablename__}.id = 8" in sql


async def test_transform_article_failure_emits_one_error_log_with_article_id(caplog):
    fake = _make_fake(9)
    article = _make_article(9)
    mock_local, _ = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(side_effect=TimeoutError("boom")),
        caplog.at_level(logging.ERROR, logger="app.workers.transform"),
    ):
        await transform_article({}, article_id=9)

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(error_records) == 1
    msg = error_records[0].getMessage()
    assert "9" in msg
    assert "TimeoutError" in msg


async def test_transform_article_failure_does_not_propagate_exception():
    fake = _make_fake(10)
    article = _make_article(10)
    mock_local, _ = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(side_effect=Exception("explode")),
    ):
        # Must not raise.
        await transform_article({}, article_id=10)


# ---------------------------------------------------------------------------
# Logging safety — never reveal prompt / response / api key
# ---------------------------------------------------------------------------


async def test_transform_article_failure_log_does_not_contain_prompt_response_or_api_key(  # noqa: E501
    caplog,
):
    fake = _make_fake(11)
    article = _make_article(
        11, title="SECRET TITLE TEXT", description="SECRET DESC TEXT"
    )
    mock_local, _ = _make_session_cm(get_returns=[fake, article])

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(side_effect=Exception("explode")),
        caplog.at_level(logging.DEBUG, logger="app.workers.transform"),
    ):
        await transform_article({}, article_id=11)

    for record in caplog.records:
        msg = record.getMessage()
        assert "SECRET TITLE TEXT" not in msg
        assert "SECRET DESC TEXT" not in msg
        assert settings.openai_api_key not in msg


async def test_transform_article_success_log_does_not_contain_prompt_response_or_api_key(  # noqa: E501
    caplog,
):
    fake = _make_fake(12)
    article = _make_article(
        12, title="SECRET TITLE TEXT", description="SECRET DESC TEXT"
    )
    mock_local, _ = _make_session_cm(get_returns=[fake, article])
    pair = SatiricalPair(title="RESPONSE TITLE TEXT", description="RESPONSE DESC TEXT")

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        _patch_service(return_pair=pair),
        caplog.at_level(logging.DEBUG, logger="app.workers.transform"),
    ):
        await transform_article({}, article_id=12)

    for record in caplog.records:
        msg = record.getMessage()
        assert "SECRET TITLE TEXT" not in msg
        assert "SECRET DESC TEXT" not in msg
        assert "RESPONSE TITLE TEXT" not in msg
        assert "RESPONSE DESC TEXT" not in msg
        assert settings.openai_api_key not in msg


# ---------------------------------------------------------------------------
# WorkerSettings sanity
# ---------------------------------------------------------------------------


def test_worker_settings_max_tries_is_one():
    assert WorkerSettings.max_tries == 1


def test_worker_settings_functions_contains_transform_article():
    assert transform_article in WorkerSettings.functions
