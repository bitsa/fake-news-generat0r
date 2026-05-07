import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.arq_client import get_arq_pool
from app.config import settings
from app.db import get_session
from app.exceptions import NotFoundError
from app.models import Article
from app.schemas.chat import ChatHistoryResponse, ChatMessageOut
from app.services.chat_generator import MOCK_REPLY
from app.services.chat_llm import STREAM_FAILURE_SENTINEL
from app.services.scraper import IngestResult
from app.sources import Source


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


class _PostHarness:
    """Wires get_session + AsyncSessionLocal so we can assert persistence
    side-effects of POST /api/articles/{id}/chat without hitting Postgres."""

    def __init__(self, app, *, article_exists: bool):
        self.app = app
        self.article_exists = article_exists
        self.request_session = AsyncMock()
        self.request_session.scalar = AsyncMock(
            return_value=1 if article_exists else None
        )
        self.request_session.add = MagicMock()
        self.assistant_session = AsyncMock()
        self.assistant_session.add = MagicMock()
        # The streaming generator opens AsyncSessionLocal twice: once as the
        # chat_llm read_session (article + fake + history) and once for the
        # assistant-row write. Both opens reuse the same captured session.
        article = Article(
            id=1,
            source=Source.NYT,
            title="orig title",
            description="orig description",
            url="http://example.com/a/1",
        )
        self.assistant_session.get = AsyncMock(return_value=article)
        fake_result = MagicMock()
        fake_result.scalar_one_or_none = MagicMock(return_value=None)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []
        self.assistant_session.execute = AsyncMock(
            side_effect=[fake_result, history_result]
        )
        self._cm = MagicMock()
        self._cm.__aenter__ = AsyncMock(return_value=self.assistant_session)
        self._cm.__aexit__ = AsyncMock(return_value=None)
        self._factory = MagicMock(return_value=self._cm)
        self._patch = None

    def __enter__(self):
        async def override_get_session():
            yield self.request_session

        self.app.dependency_overrides[get_session] = override_get_session
        self._patch = patch("app.services.chat.AsyncSessionLocal", self._factory)
        self._patch.__enter__()
        return self

    def __exit__(self, *args):
        self._patch.__exit__(*args)
        self.app.dependency_overrides.pop(get_session, None)
        return False


def _parse_sse(body: bytes) -> list[dict | str]:
    events: list[dict | str] = []
    for raw_event in body.split(b"\n\n"):
        raw_event = raw_event.strip()
        if not raw_event:
            continue
        if not raw_event.startswith(b"data: "):
            continue
        payload = raw_event[len(b"data: ") :].decode()
        if payload == "[DONE]":
            events.append("[DONE]")
        else:
            events.append(json.loads(payload))
    return events


# ---- existing GET history tests (preserved) ----


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


async def test_get_chat_history_unchanged_status_and_shape_after_post_endpoint_added(
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
    assert set(body["messages"][0].keys()) == {
        "id",
        "role",
        "content",
        "is_error",
        "request_id",
        "created_at",
    }


# ---- POST /api/articles/{id}/chat — endpoint surface (AC1) ----


async def test_post_chat_registered_under_api_prefix(chat_client, app):
    with _PostHarness(app, article_exists=True):
        ok = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
        unprefixed = await chat_client.post("/articles/1/chat", json={"message": "hi"})

    assert ok.status_code == 200
    assert unprefixed.status_code == 404


# ---- AC2 — body validation ----


async def test_post_chat_rejects_missing_message_with_422(chat_client, app):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={})
    assert r.status_code == 422
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


async def test_post_chat_rejects_non_string_message_with_422(chat_client, app):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": 42})
    assert r.status_code == 422
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


async def test_post_chat_rejects_empty_string_message_with_422(chat_client, app):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": ""})
    assert r.status_code == 422
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


async def test_post_chat_rejects_whitespace_only_message_with_422(chat_client, app):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": "   \t\n"})
    assert r.status_code == 422
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


async def test_post_chat_rejects_message_longer_than_max_chars_with_422(
    chat_client, app
):
    too_long = "x" * (settings.chat_message_max_chars + 1)
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": too_long})
    assert r.status_code == 422
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


async def test_post_chat_accepts_message_at_exact_max_chars_boundary(chat_client, app):
    boundary = "x" * settings.chat_message_max_chars
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": boundary})
    assert r.status_code == 200
    persisted = h.request_session.add.call_args.args[0]
    assert persisted.content == boundary


async def test_post_chat_sanitizes_user_message_before_persisting(chat_client, app):
    raw = "  hello   world  "
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": raw})
    assert r.status_code == 200
    assert h.request_session.add.call_args.args[0].content == "hello world"


async def test_post_chat_strips_html_tags_from_user_message_before_persisting(
    chat_client, app
):
    raw = "click <a href='x'>here</a> &amp; win"
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": raw})
    assert r.status_code == 200
    persisted = h.request_session.add.call_args.args[0].content
    assert "<" not in persisted
    assert "&amp;" not in persisted
    assert "click" in persisted
    assert "here" in persisted


async def test_post_chat_returns_422_when_sanitization_yields_empty_string(
    chat_client, app
):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": "<p></p>"})
    assert r.status_code == 422
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


# ---- AC3 — missing article ----


async def test_post_chat_returns_404_with_detail_for_missing_article(chat_client, app):
    with _PostHarness(app, article_exists=False):
        r = await chat_client.post("/api/articles/999/chat", json={"message": "hi"})
    assert r.status_code == 404
    assert r.json() == {"detail": "Article 999 not found"}


async def test_post_chat_inserts_no_rows_on_404_missing_article(chat_client, app):
    with _PostHarness(app, article_exists=False) as h:
        await chat_client.post("/api/articles/999/chat", json={"message": "hi"})
    h.request_session.add.assert_not_called()
    h.assistant_session.add.assert_not_called()


async def test_post_chat_does_not_open_sse_stream_on_404(chat_client, app):
    with _PostHarness(app, article_exists=False):
        r = await chat_client.post("/api/articles/999/chat", json={"message": "hi"})
    assert r.headers.get("content-type", "").startswith("application/json")


# ---- AC4 — happy-path response shape ----


async def test_post_chat_happy_path_status_200(chat_client, app):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.status_code == 200


async def test_post_chat_happy_path_content_type_is_event_stream(chat_client, app):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.headers["content-type"].startswith("text/event-stream")


async def test_post_chat_happy_path_sets_cache_control_no_cache_header(
    chat_client, app
):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.headers["cache-control"] == "no-cache"


async def test_post_chat_happy_path_sets_x_accel_buffering_no_header(chat_client, app):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.headers["x-accel-buffering"] == "no"


async def test_post_chat_happy_path_sets_connection_keep_alive_header(chat_client, app):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.headers["connection"] == "keep-alive"


# ---- AC5 — token event encoding ----


async def test_post_chat_each_token_event_is_data_token_json_with_double_newline(
    chat_client, app
):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    body = r.content
    assert b"\n\n" in body
    events = _parse_sse(body)
    token_events = [e for e in events if isinstance(e, dict) and "token" in e]
    assert token_events
    for e in token_events:
        assert set(e.keys()) == {"token"}
        assert isinstance(e["token"], str)


async def test_post_chat_concatenated_token_chunks_equal_full_assistant_reply(
    chat_client, app
):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    events = _parse_sse(r.content)
    tokens = [e["token"] for e in events if isinstance(e, dict) and "token" in e]
    assert "".join(tokens) == MOCK_REPLY


# ---- AC6 — [DONE] terminator ----


async def test_post_chat_happy_path_emits_exactly_one_done_event_after_last_token(
    chat_client, app
):
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    events = _parse_sse(r.content)
    done_indexes = [i for i, e in enumerate(events) if e == "[DONE]"]
    assert len(done_indexes) == 1
    assert done_indexes[0] == len(events) - 1


async def test_post_chat_error_path_emits_no_done_event(chat_client, app):
    with (
        _PostHarness(app, article_exists=True),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "boom"})
    events = _parse_sse(r.content)
    assert "[DONE]" not in events


# ---- AC7 — error event framing ----


async def test_post_chat_error_path_emits_exactly_one_error_event_then_closes(
    chat_client, app
):
    with (
        _PostHarness(app, article_exists=True),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "boom"})
    events = _parse_sse(r.content)
    error_events = [e for e in events if isinstance(e, dict) and "error" in e]
    assert len(error_events) == 1
    assert events[-1] == error_events[0]


async def test_post_chat_error_event_payload_does_not_contain_exception_class_name(
    chat_client, app
):
    with (
        _PostHarness(app, article_exists=True),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "boom"})
    events = _parse_sse(r.content)
    error_event = next(e for e in events if isinstance(e, dict) and "error" in e)
    payload = error_event["error"]
    assert "MockChatError" not in payload
    assert "RuntimeError" not in payload
    assert "Traceback" not in payload


# ---- AC8 — user row committed before stream opens ----


async def test_post_chat_user_row_committed_before_stream_opens_with_verbatim_content(
    chat_client, app
):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post(
            "/api/articles/1/chat", json={"message": "verbatim msg"}
        )

    assert r.status_code == 200
    assert h.request_session.add.call_count == 1
    user_row = h.request_session.add.call_args.args[0]
    assert user_row.role == "user"
    assert user_row.content == "verbatim msg"
    assert user_row.is_error is False
    h.request_session.commit.assert_awaited()


# ---- AC9 — assistant row committed before stream closes ----


async def test_post_chat_assistant_row_content_equals_concatenated_token_chunks(
    chat_client, app
):
    with _PostHarness(app, article_exists=True) as h:
        await chat_client.post("/api/articles/1/chat", json={"message": "hi"})

    assert h.assistant_session.add.call_count == 1
    assistant_row = h.assistant_session.add.call_args.args[0]
    assert assistant_row.role == "assistant"
    assert assistant_row.is_error is False
    assert assistant_row.content == MOCK_REPLY


async def test_post_chat_assistant_row_committed_before_done_event(chat_client, app):
    with _PostHarness(app, article_exists=True) as h:
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})

    body_done_index = r.content.index(b"data: [DONE]\n\n")
    assert body_done_index >= 0
    h.assistant_session.commit.assert_awaited_once()


# ---- AC10 — GET history reflects exchange after happy POST ----


async def test_get_chat_history_after_happy_post_returns_user_then_assistant_in_order(
    chat_client, app
):
    user_msg = _msg_out(
        id=1,
        role="user",
        content="hi",
        is_error=False,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )
    assistant_msg = _msg_out(
        id=2,
        role="assistant",
        content=MOCK_REPLY,
        is_error=False,
        created_at=datetime(2026, 5, 1, 12, 0, 30, tzinfo=UTC),
    )
    response = ChatHistoryResponse(article_id=1, messages=[user_msg, assistant_msg])

    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert [m["is_error"] for m in msgs] == [False, False]
    assert msgs[0]["content"] == "hi"
    assert msgs[1]["content"] == MOCK_REPLY


# ---- AC11 — error path persistence ----


async def test_post_chat_error_path_writes_exactly_one_assistant_row_with_is_error_true(
    chat_client, app
):
    with (
        _PostHarness(app, article_exists=True) as h,
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        await chat_client.post("/api/articles/1/chat", json={"message": "boom"})

    assert h.assistant_session.add.call_count == 1
    row = h.assistant_session.add.call_args.args[0]
    assert row.role == "assistant"
    assert row.is_error is True


async def test_post_chat_error_path_does_not_modify_user_row(chat_client, app):
    with (
        _PostHarness(app, article_exists=True) as h,
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        await chat_client.post("/api/articles/1/chat", json={"message": "boom"})

    assert h.request_session.add.call_count == 1
    user_row = h.request_session.add.call_args.args[0]
    assert user_row.role == "user"
    assert user_row.content == "boom"
    assert user_row.is_error is False


# ---- AC12 — sentinel parity ----


async def test_post_chat_error_sentinel_string_byte_equal_in_sse_and_persisted_row(
    chat_client, app
):
    with (
        _PostHarness(app, article_exists=True) as h,
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "boom"})

    events = _parse_sse(r.content)
    error_event = next(e for e in events if isinstance(e, dict) and "error" in e)
    sse_payload = error_event["error"]
    persisted = h.assistant_session.add.call_args.args[0].content
    assert sse_payload == STREAM_FAILURE_SENTINEL
    assert persisted == STREAM_FAILURE_SENTINEL
    assert sse_payload.encode() == persisted.encode()


async def test_post_chat_error_sentinel_does_not_contain_traceback_or_class_name(
    chat_client, app
):
    with (
        _PostHarness(app, article_exists=True),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "boom"})

    events = _parse_sse(r.content)
    error_event = next(e for e in events if isinstance(e, dict) and "error" in e)
    payload = error_event["error"]
    assert "Traceback" not in payload
    assert "MockChatError" not in payload
    assert "RuntimeError" not in payload


# ---- AC13 — GET history after error POST ----


async def test_get_chat_history_after_error_post_returns_user_false_then_assistant_true(
    chat_client, app
):
    user_msg = _msg_out(
        id=1,
        role="user",
        content="boom",
        is_error=False,
        created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )
    assistant_msg = _msg_out(
        id=2,
        role="assistant",
        content=STREAM_FAILURE_SENTINEL,
        is_error=True,
        created_at=datetime(2026, 5, 1, 12, 0, 30, tzinfo=UTC),
    )
    response = ChatHistoryResponse(article_id=1, messages=[user_msg, assistant_msg])

    with patch(
        "app.routers.chat.chat_service.get_chat_history",
        new=AsyncMock(return_value=response),
    ):
        r = await chat_client.get("/api/articles/1/chat")

    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert [m["is_error"] for m in msgs] == [False, True]
    assert msgs[1]["content"] == STREAM_FAILURE_SENTINEL


# ---- AC16 — works with placeholder OPENAI_API_KEY ----


async def test_post_chat_works_with_placeholder_openai_api_key(chat_client, app):
    assert settings.openai_api_key.startswith("sk-")
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.status_code == 200
    events = _parse_sse(r.content)
    assert any(isinstance(e, dict) and "token" in e for e in events)


# ---- AC19 — default force-token never triggers error branch ----


async def test_post_chat_with_default_force_token_never_takes_error_branch(
    chat_client, app
):
    assert settings.chat_mock_force_error_token is None
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "anything"})
    events = _parse_sse(r.content)
    assert "[DONE]" in events
    assert not any(isinstance(e, dict) and "error" in e for e in events)


# ---- AC22 — logging safety ----


async def test_post_chat_logs_do_not_contain_request_message_body(
    chat_client, app, caplog
):
    secret = "super-secret-message-body"
    with (
        caplog.at_level("INFO", logger="app.services.chat"),
        _PostHarness(app, article_exists=True),
    ):
        await chat_client.post("/api/articles/1/chat", json={"message": secret})

    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert secret not in log_text


async def test_post_chat_logs_do_not_contain_full_assistant_reply(
    chat_client, app, caplog
):
    with (
        caplog.at_level("INFO", logger="app.services.chat"),
        _PostHarness(app, article_exists=True),
    ):
        await chat_client.post("/api/articles/1/chat", json={"message": "hi"})

    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert MOCK_REPLY not in log_text


async def test_post_chat_error_path_logs_do_not_contain_traceback_string(
    chat_client, app, caplog
):
    with (
        caplog.at_level("ERROR", logger="app.services.chat"),
        _PostHarness(app, article_exists=True),
        patch.object(settings, "chat_mock_force_error_token", "boom"),
    ):
        await chat_client.post("/api/articles/1/chat", json={"message": "boom"})

    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "Traceback" not in log_text
    assert "boom" not in log_text


async def test_get_chat_history_post_method_returns_post_response_not_405(
    chat_client, app
):
    """Sanity check: with POST mounted, the same path now accepts POST."""
    with _PostHarness(app, article_exists=True):
        r = await chat_client.post("/api/articles/1/chat", json={"message": "hi"})
    assert r.status_code != 405
