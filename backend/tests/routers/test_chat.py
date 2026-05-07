from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.arq_client import get_arq_pool
from app.db import get_session
from app.exceptions import NotFoundError
from app.schemas.chat import ChatHistoryResponse, ChatMessageOut
from app.services.scraper import IngestResult


def _make_session_cm() -> tuple[MagicMock, AsyncMock]:
    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm, mock_session


@pytest_asyncio.fixture
async def chat_client(app):
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


def _msg_out(
    *,
    id: int = 1,
    role: str = "user",
    content: str = "hello",
    is_error: bool = False,
    request_id: str | None = None,
    created_at: datetime | None = None,
) -> ChatMessageOut:
    return ChatMessageOut(
        id=id,
        role=role,
        content=content,
        is_error=is_error,
        request_id=request_id,
        created_at=created_at or datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )


async def test_get_chat_history_registered_under_api_prefix(chat_client):
    response = ChatHistoryResponse(article_id=1, messages=[])
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        ok = await chat_client.get("/api/articles/1/chat")
        unprefixed = await chat_client.get("/articles/1/chat")

    assert ok.status_code == 200
    assert unprefixed.status_code == 404


async def test_get_chat_history_returns_404_with_detail_for_missing_article(
    chat_client,
):
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(side_effect=NotFoundError("Article 999999 not found")),
    ):
        r = await chat_client.get("/api/articles/999999/chat")

    assert r.status_code == 404
    assert r.json() == {"detail": "Article 999999 not found"}


async def test_get_chat_history_response_shape_has_exactly_two_top_level_keys(
    chat_client,
):
    response = ChatHistoryResponse(
        article_id=1,
        messages=[_msg_out(id=1, role="user", content="hi")],
    )
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"article_id", "messages"}
    assert body["article_id"] == 1


async def test_get_chat_history_each_message_has_exactly_six_required_keys(chat_client):
    response = ChatHistoryResponse(
        article_id=1,
        messages=[_msg_out(id=7, role="assistant", content="hello there")],
    )
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    msg = r.json()["messages"][0]
    assert set(msg.keys()) == {
        "id",
        "role",
        "content",
        "is_error",
        "request_id",
        "created_at",
    }
    assert msg["id"] == 7
    assert msg["role"] == "assistant"
    assert msg["content"] == "hello there"


async def test_get_chat_history_is_error_field_defaults_false_in_response(chat_client):
    response = ChatHistoryResponse(
        article_id=1,
        messages=[_msg_out(id=1, is_error=False)],
    )
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    assert r.json()["messages"][0]["is_error"] is False


async def test_get_chat_history_request_id_field_may_be_null_in_response(chat_client):
    response = ChatHistoryResponse(
        article_id=1,
        messages=[_msg_out(id=1, request_id=None)],
    )
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    assert r.json()["messages"][0]["request_id"] is None


async def test_get_chat_history_created_at_serialised_iso8601_with_timezone(
    chat_client,
):
    response = ChatHistoryResponse(
        article_id=1,
        messages=[
            _msg_out(id=1, created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC)),
        ],
    )
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    created_at = r.json()["messages"][0]["created_at"]
    assert isinstance(created_at, str)
    assert created_at.endswith("+00:00") or created_at.endswith("Z")


async def test_get_chat_history_no_auth_required_returns_200(chat_client):
    response = ChatHistoryResponse(article_id=1, messages=[])
    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    assert r.status_code == 200
    assert "WWW-Authenticate" not in r.headers


async def test_get_chat_history_post_method_returns_405_method_not_allowed(chat_client):
    r = await chat_client.post("/api/articles/1/chat", json={"content": "hi"})
    assert r.status_code == 405
