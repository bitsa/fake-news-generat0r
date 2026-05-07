from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import NotFoundError
from app.models import ChatMessage
from app.services.chat import get_chat_history


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
    # Service trusts SQL ORDER BY — caller returns rows in DB-sorted order.
    session = _make_session(article_id_returned=1, rows=[first, second])

    response = await get_chat_history(session, 1)

    assert [m.id for m in response.messages] == [10, 11]
