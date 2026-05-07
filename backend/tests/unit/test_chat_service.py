from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.exceptions import NotFoundError
from app.models import Article, ChatMessage
from app.schemas.chat import ChatPostRequest
from app.services.chat import get_chat_history, post_chat_stream
from app.services.chat_generator import MOCK_REPLY
from app.services.chat_llm import STREAM_FAILURE_SENTINEL
from app.sources import Source


def _msg(
    *,
    id: int,
    article_id: int = 1,
    role: str = "user",
    content: str = "hi",
    is_error: bool = False,
    request_id: str | None = None,
    created_at: datetime,
) -> ChatMessage:
    return ChatMessage(
        id=id,
        article_id=article_id,
        role=role,
        content=content,
        is_error=is_error,
        request_id=request_id,
        created_at=created_at,
    )


def _make_session(*, article_id_returned: int | None, rows: list[ChatMessage]):
    session = AsyncMock()
    session.scalar.return_value = article_id_returned
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = rows
    session.execute.return_value = mock_result
    return session


def _make_request_session(*, article_id_returned: int | None):
    session = AsyncMock()
    session.scalar.return_value = article_id_returned
    session.add = MagicMock()
    return session


def _make_assistant_session_factory():
    """Return (mock_AsyncSessionLocal, captured_session) where captured_session
    is the AsyncMock used by both chat_llm.token_stream (article + fake +
    history reads) and the inner _stream_assistant assistant-row writes.
    The streaming generator opens AsyncSessionLocal twice (once for the
    chat_llm read session, once for the assistant write); both calls
    return this same captured AsyncMock."""
    captured_session = AsyncMock()
    captured_session.add = MagicMock()

    article = Article(
        id=1,
        source=Source.NYT,
        title="orig title",
        description="orig description",
        url="http://example.com/a/1",
    )
    captured_session.get = AsyncMock(return_value=article)

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = []
    captured_session.execute = AsyncMock(side_effect=[fake_result, history_result])

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=captured_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=cm)
    return factory, captured_session


# ---- existing GET history tests (unchanged) ----


async def test_chat_service_returns_messages_in_chronological_order():
    user_msg = _msg(
        id=1,
        role="user",
        content="hello",
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )
    assistant_msg = _msg(
        id=2,
        role="assistant",
        content="hi",
        created_at=datetime(2026, 5, 1, 12, 0, 30, tzinfo=UTC),
    )
    session = _make_session(article_id_returned=1, rows=[user_msg, assistant_msg])

    response = await get_chat_history(session, 1)

    assert response.article_id == 1
    assert [m.id for m in response.messages] == [1, 2]
    assert [m.role for m in response.messages] == ["user", "assistant"]


async def test_chat_service_returns_empty_messages_for_article_with_no_messages():
    session = _make_session(article_id_returned=42, rows=[])

    response = await get_chat_history(session, 42)

    assert response.article_id == 42
    assert response.messages == []


async def test_chat_service_raises_not_found_error_for_missing_article():
    session = _make_session(article_id_returned=None, rows=[])

    with pytest.raises(NotFoundError) as exc_info:
        await get_chat_history(session, 999999)

    assert "Article 999999 not found" in str(exc_info.value.message)
    assert exc_info.value.status_code == 404


async def test_chat_service_tie_break_orders_identical_created_at_by_ascending_id():
    same_time = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    first = _msg(id=10, role="user", content="a", created_at=same_time)
    second = _msg(id=11, role="assistant", content="b", created_at=same_time)
    session = _make_session(article_id_returned=1, rows=[first, second])

    response = await get_chat_history(session, 1)

    assert [m.id for m in response.messages] == [10, 11]


# ---- post_chat_stream orchestration ----


async def test_post_chat_stream_raises_not_found_when_article_missing():
    session = _make_request_session(article_id_returned=None)

    with pytest.raises(NotFoundError) as exc_info:
        await post_chat_stream(session, 999999, ChatPostRequest(message="hi"))

    assert "Article 999999 not found" in exc_info.value.message
    session.add.assert_not_called()
    session.commit.assert_not_called()


async def test_post_chat_stream_commits_user_row_before_returning_response():
    session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    with patch("app.services.chat.AsyncSessionLocal", factory):
        response = await post_chat_stream(session, 1, ChatPostRequest(message="hi"))

    assert session.add.call_count == 1
    added = session.add.call_args.args[0]
    assert isinstance(added, ChatMessage)
    assert added.role == "user"
    assert added.content == "hi"
    assert added.is_error is False
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["connection"] == "keep-alive"


async def test_post_chat_stream_sanitizes_message_before_persisting():
    raw = "  spaces  around   "
    session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    with patch("app.services.chat.AsyncSessionLocal", factory):
        await post_chat_stream(session, 1, ChatPostRequest(message=raw))

    assert session.add.call_args.args[0].content == "spaces around"


async def test_post_chat_stream_strips_html_tags_from_user_message():
    raw = "Hello <b>world</b> &amp; friends"
    session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    with patch("app.services.chat.AsyncSessionLocal", factory):
        await post_chat_stream(session, 1, ChatPostRequest(message=raw))

    persisted = session.add.call_args.args[0].content
    assert "<" not in persisted
    assert "&amp;" not in persisted
    assert "Hello" in persisted
    assert "world" in persisted


async def test_post_chat_stream_raises_422_when_sanitization_yields_empty():
    raw = "<p></p>"
    session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    from app.exceptions import ValidationError

    with patch("app.services.chat.AsyncSessionLocal", factory):
        with pytest.raises(ValidationError) as exc_info:
            await post_chat_stream(session, 1, ChatPostRequest(message=raw))

    assert exc_info.value.status_code == 422
    session.add.assert_not_called()


async def test_post_chat_stream_assistant_row_content_equals_concatenated_tokens():
    session = _make_request_session(article_id_returned=1)
    factory, captured = _make_assistant_session_factory()

    with patch("app.services.chat.AsyncSessionLocal", factory):
        response = await post_chat_stream(session, 1, ChatPostRequest(message="hi"))
        body = b"".join([chunk async for chunk in response.body_iterator])

    assert b"data: [DONE]\n\n" in body
    assert captured.add.call_count == 1
    assistant_row = captured.add.call_args.args[0]
    assert assistant_row.role == "assistant"
    assert assistant_row.is_error is False
    assert assistant_row.content == MOCK_REPLY
    captured.commit.assert_awaited_once()


async def test_post_chat_stream_error_path_writes_assistant_row_with_sentinel():
    session = _make_request_session(article_id_returned=1)
    factory, captured = _make_assistant_session_factory()

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        response = await post_chat_stream(session, 1, ChatPostRequest(message="boom"))
        body = b"".join([chunk async for chunk in response.body_iterator])

    assert b"[DONE]" not in body
    assert b'"error"' in body
    assert STREAM_FAILURE_SENTINEL.encode() in body
    assert captured.add.call_count == 1
    assistant_row = captured.add.call_args.args[0]
    assert assistant_row.role == "assistant"
    assert assistant_row.is_error is True
    assert assistant_row.content == STREAM_FAILURE_SENTINEL
    captured.commit.assert_awaited_once()


async def test_post_chat_stream_error_sentinel_byte_equal_in_sse_and_persisted_row():
    session = _make_request_session(article_id_returned=1)
    factory, captured = _make_assistant_session_factory()

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        response = await post_chat_stream(session, 1, ChatPostRequest(message="boom"))
        body = b"".join([chunk async for chunk in response.body_iterator])

    assistant_row = captured.add.call_args.args[0]
    assert STREAM_FAILURE_SENTINEL.encode() in body
    assert assistant_row.content == STREAM_FAILURE_SENTINEL


async def test_post_chat_stream_logs_omit_message_body_and_full_reply(caplog):
    session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    secret = "super secret message body do-not-log"
    with (
        caplog.at_level("INFO", logger="app.services.chat"),
        patch("app.services.chat.AsyncSessionLocal", factory),
    ):
        response = await post_chat_stream(session, 1, ChatPostRequest(message=secret))
        async for _ in response.body_iterator:
            pass

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in log_text
    assert MOCK_REPLY not in log_text


async def test_post_chat_stream_error_logs_omit_traceback_and_message_body(caplog):
    session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    secret = "force-token-secret"
    with (
        caplog.at_level("ERROR", logger="app.services.chat"),
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch.object(settings, "chat_mock_force_error_token", secret),
    ):
        response = await post_chat_stream(session, 1, ChatPostRequest(message=secret))
        async for _ in response.body_iterator:
            pass

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in log_text
    assert "Traceback" not in log_text
