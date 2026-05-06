import logging
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.workers.transform import MOCK_DESCRIPTION, MOCK_TITLE, transform_article


def _make_session_cm(fake=None):
    """Return a (mock_session_local_callable, mock_session) pair."""
    mock_session = AsyncMock()
    mock_session.get.return_value = fake

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_local = MagicMock(return_value=mock_cm)
    return mock_local, mock_session


def _make_fake(article_id: int = 1):
    fake = MagicMock()
    fake.article_id = article_id
    return fake


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_transform_article_sets_completed_status_and_fills_mock_content():
    fake = _make_fake(1)
    mock_local, mock_session = _make_session_cm(fake=fake)

    with patch("app.workers.transform.AsyncSessionLocal", mock_local):
        await transform_article({}, article_id=1)

    assert fake.title == MOCK_TITLE
    assert fake.description == MOCK_DESCRIPTION
    assert fake.title  # non-null, non-empty
    assert fake.description  # non-null, non-empty
    assert fake.transform_status == "completed"
    mock_session.commit.assert_awaited_once()


async def test_transform_article_completed_row_model_equals_settings_openai_model_transform():  # noqa: E501
    fake = _make_fake(1)
    mock_local, _ = _make_session_cm(fake=fake)

    with patch("app.workers.transform.AsyncSessionLocal", mock_local):
        await transform_article({}, article_id=1)

    assert fake.model == settings.openai_model_transform


async def test_transform_article_completed_row_temperature_equals_settings_openai_temperature_transform():  # noqa: E501
    fake = _make_fake(1)
    mock_local, _ = _make_session_cm(fake=fake)

    with patch("app.workers.transform.AsyncSessionLocal", mock_local):
        await transform_article({}, article_id=1)

    assert fake.temperature == settings.openai_temperature_transform


# ---------------------------------------------------------------------------
# Non-existent article_id
# ---------------------------------------------------------------------------


async def test_transform_article_skips_nonexistent_article_id_without_raising():
    mock_local, mock_session = _make_session_cm(fake=None)

    with patch("app.workers.transform.AsyncSessionLocal", mock_local):
        # Must not raise
        await transform_article({}, article_id=999)

    mock_session.commit.assert_not_called()


async def test_transform_article_skips_nonexistent_article_id_logs_skip_event(caplog):
    mock_local, _ = _make_session_cm(fake=None)

    with (
        patch("app.workers.transform.AsyncSessionLocal", mock_local),
        caplog.at_level(logging.INFO, logger="app.workers.transform"),
    ):
        await transform_article({}, article_id=42)

    skip_records = [r for r in caplog.records if "skip" in r.message]
    assert len(skip_records) == 1
    assert "42" in skip_records[0].message


# ---------------------------------------------------------------------------
# Exception path
# ---------------------------------------------------------------------------


async def test_transform_article_deletes_fake_row_on_unexpected_exception():
    fake = _make_fake(article_id=7)
    mock_local, mock_session = _make_session_cm(fake=fake)
    # First commit raises; second commit (after delete) succeeds
    mock_session.commit.side_effect = [Exception("db flake"), None]

    with patch("app.workers.transform.AsyncSessionLocal", mock_local):
        await transform_article({}, article_id=7)

    mock_session.rollback.assert_awaited_once()
    # execute called for the targeted delete
    assert mock_session.execute.await_count == 1
    # second commit persists the deletion
    assert mock_session.commit.await_count == 2


async def test_transform_article_preserves_article_row_when_fake_deleted_on_exception():
    fake = _make_fake(article_id=8)
    mock_local, mock_session = _make_session_cm(fake=fake)
    mock_session.commit.side_effect = [Exception("flake"), None]

    with patch("app.workers.transform.AsyncSessionLocal", mock_local):
        await transform_article({}, article_id=8)

    # Only one execute call — the targeted ArticleFake delete; articles table untouched
    assert mock_session.execute.await_count == 1
