import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.exceptions import NotFoundError
from app.models import Article, ArticleFake, ChatMessage
from app.schemas.chat import ChatPostRequest
from app.services import chat_llm
from app.services.chat import post_chat_stream
from app.services.chat_generator import MOCK_REPLY
from app.services.chat_llm import (
    STREAM_FAILURE_SENTINEL,
    SYSTEM_PROMPT,
    build_chat_messages,
    token_stream,
)
from app.sources import Source

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_article(
    *,
    id: int = 1,
    title: str = "orig title",
    description: str = "orig description",
) -> Article:
    return Article(
        id=id,
        source=Source.NYT,
        title=title,
        description=description,
        url=f"http://example.com/a/{id}",
    )


def _make_fake(
    *,
    article_id: int = 1,
    transform_status: str = "completed",
    title: str | None = "satirical title",
    description: str | None = "satirical description",
) -> ArticleFake:
    return ArticleFake(
        article_id=article_id,
        transform_status=transform_status,
        title=title,
        description=description,
    )


def _msg(
    *,
    id: int,
    role: str = "user",
    content: str = "hi",
    is_error: bool = False,
    created_at: datetime | None = None,
    article_id: int = 1,
) -> ChatMessage:
    return ChatMessage(
        id=id,
        article_id=article_id,
        role=role,
        content=content,
        is_error=is_error,
        created_at=created_at or datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
    )


class _FakeStream:
    """Async-iterable fake of openai's streaming response object."""

    def __init__(self, deltas: list[str | None], raise_at: int | None = None):
        self._deltas = deltas
        self._raise_at = raise_at
        self._exc: BaseException | None = None

    def with_exception_at(self, idx: int, exc: BaseException) -> "_FakeStream":
        self._raise_at = idx
        self._exc = exc
        return self

    def __aiter__(self):
        async def gen():
            for i, content in enumerate(self._deltas):
                if self._raise_at is not None and i == self._raise_at:
                    raise self._exc or RuntimeError("mid-stream")
                chunk = MagicMock()
                delta = MagicMock()
                delta.content = content
                choice = MagicMock()
                choice.delta = delta
                chunk.choices = [choice]
                yield chunk

        return gen()


def _make_async_openai(stream: _FakeStream | BaseException):
    """Build a patchable AsyncOpenAI class whose
    chat.completions.create returns the given fake stream (or raises)."""
    create_mock = AsyncMock()
    if isinstance(stream, BaseException):
        create_mock.side_effect = stream
    else:
        create_mock.return_value = stream
    instance = MagicMock()
    instance.chat.completions.create = create_mock
    cls = MagicMock(return_value=instance)
    return cls, create_mock


def _make_read_session(
    *,
    article: Article | None = None,
    fake: ArticleFake | None = None,
    history_rows: list[ChatMessage] | None = None,
):
    """Build an AsyncMock session that responds to chat_llm.token_stream's
    article.get + ArticleFake fetch + ChatMessage history fetch."""
    session = AsyncMock()
    session.get = AsyncMock(
        return_value=article if article is not None else _make_article()
    )
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake)
    history_result = MagicMock()
    # token_stream loads history DESC then reverses to ASC.
    rows_desc = sorted(
        history_rows or [], key=lambda r: (r.created_at, r.id), reverse=True
    )
    history_result.scalars.return_value.all.return_value = rows_desc
    session.execute = AsyncMock(side_effect=[fake_result, history_result])
    return session


# ---------------------------------------------------------------------------
# Real-call path
# ---------------------------------------------------------------------------


async def test_real_call_invokes_chat_completions_create_exactly_once(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    fake_stream = _FakeStream(["hello", " world"])
    cls, create_mock = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        chunks = [
            c
            async for c in chat_llm._stream_real_llm(
                [{"role": "user", "content": "hi"}]
            )
        ]

    assert chunks == ["hello", " world"]
    create_mock.assert_awaited_once()


async def test_real_call_uses_openai_model_chat_setting(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    monkeypatch.setattr(settings, "openai_model_chat", "gpt-test-A")
    fake_stream = _FakeStream(["x"])
    cls, create_mock = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        async for _ in chat_llm._stream_real_llm([{"role": "user", "content": "hi"}]):
            pass

    assert create_mock.await_args.kwargs["model"] == "gpt-test-A"


async def test_real_call_uses_openai_temperature_chat_setting(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    monkeypatch.setattr(settings, "openai_temperature_chat", 0.42)
    fake_stream = _FakeStream(["x"])
    cls, create_mock = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        async for _ in chat_llm._stream_real_llm([{"role": "user", "content": "hi"}]):
            pass

    assert create_mock.await_args.kwargs["temperature"] == 0.42


async def test_real_call_passes_chat_max_output_tokens_as_max_tokens(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    monkeypatch.setattr(settings, "chat_max_output_tokens", 321)
    fake_stream = _FakeStream(["x"])
    cls, create_mock = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        async for _ in chat_llm._stream_real_llm([{"role": "user", "content": "hi"}]):
            pass

    assert create_mock.await_args.kwargs["max_tokens"] == 321


async def test_real_call_passes_openai_request_timeout_seconds_to_client(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    monkeypatch.setattr(settings, "openai_request_timeout_seconds", 17)
    fake_stream = _FakeStream(["x"])
    cls, _ = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        async for _ in chat_llm._stream_real_llm([{"role": "user", "content": "hi"}]):
            pass

    cls.assert_called_once()
    assert cls.call_args.kwargs["timeout"] == 17


async def test_real_call_uses_chat_completions_create_with_stream_true_not_beta_parse(
    monkeypatch,
):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    fake_stream = _FakeStream(["x"])
    cls, create_mock = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        async for _ in chat_llm._stream_real_llm([{"role": "user", "content": "hi"}]):
            pass

    instance = cls.return_value
    assert create_mock.await_args.kwargs["stream"] is True
    instance.beta.chat.completions.parse.assert_not_called()


async def test_real_stream_emits_each_non_empty_delta_as_token_string(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    fake_stream = _FakeStream(["alpha", "beta", "gamma"])
    cls, _ = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        chunks = [c async for c in chat_llm._stream_real_llm([])]

    assert chunks == ["alpha", "beta", "gamma"]


async def test_real_stream_skips_empty_and_none_deltas(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    fake_stream = _FakeStream(["alpha", "", "  ", None, "beta"])
    cls, _ = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        chunks = [c async for c in chat_llm._stream_real_llm([])]

    assert chunks == ["alpha", "  ", "beta"]


async def test_real_stream_concatenated_yielded_chunks_equal_full_assistant_text(
    monkeypatch,
):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    fake_stream = _FakeStream(["Hello, ", "world", "."])
    cls, _ = _make_async_openai(fake_stream)

    with patch("openai.AsyncOpenAI", cls):
        chunks = [c async for c in chat_llm._stream_real_llm([])]

    assert "".join(chunks) == "Hello, world."


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def test_prompt_builder_emits_system_then_history_then_final_user_message_in_order():
    article = _make_article()
    history = [
        _msg(
            id=1,
            role="user",
            content="prior q",
            created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        ),
        _msg(
            id=2,
            role="assistant",
            content="prior a",
            created_at=datetime(2026, 5, 1, 12, 1, tzinfo=UTC),
        ),
    ]
    msgs = build_chat_messages(article, None, history, "new q", history_window=10)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "prior q"
    assert msgs[2]["content"] == "prior a"
    assert msgs[3]["content"] == "new q"


def test_prompt_system_message_is_stable_across_runs_for_same_input():
    article = _make_article()
    a = build_chat_messages(article, None, [], "q", history_window=10)[0]["content"]
    b = build_chat_messages(article, None, [], "q", history_window=10)[0]["content"]
    assert a == b


def test_prompt_builder_includes_original_article_title_and_description_in_system_message():  # noqa: E501
    article = _make_article(title="UNIQUE_T", description="UNIQUE_D")
    msgs = build_chat_messages(article, None, [], "q", history_window=10)
    sys_msg = msgs[0]["content"]
    assert "UNIQUE_T" in sys_msg
    assert "UNIQUE_D" in sys_msg


def test_prompt_builder_includes_satirical_title_and_description_when_fake_completed():
    article = _make_article()
    fake = _make_fake(title="SAT_T", description="SAT_D", transform_status="completed")
    msgs = build_chat_messages(article, fake, [], "q", history_window=10)
    sys_msg = msgs[0]["content"]
    assert "SAT_T" in sys_msg
    assert "SAT_D" in sys_msg


def test_prompt_builder_includes_only_original_when_fake_is_none():
    article = _make_article(title="ORIG_T", description="ORIG_D")
    msgs = build_chat_messages(article, None, [], "q", history_window=10)
    sys_msg = msgs[0]["content"]
    assert "ORIG_T" in sys_msg
    assert "ORIG_D" in sys_msg
    assert "Satirical rewrite title:" not in sys_msg
    assert "Satirical rewrite description:" not in sys_msg


def test_prompt_builder_includes_only_original_when_fake_status_is_pending():
    article = _make_article()
    fake = _make_fake(transform_status="pending", title=None, description=None)
    msgs = build_chat_messages(article, fake, [], "q", history_window=10)
    sys_msg = msgs[0]["content"]
    assert "Satirical rewrite title:" not in sys_msg
    assert "Satirical rewrite description:" not in sys_msg


def test_prompt_builder_orders_history_chronologically_oldest_first_by_created_at_then_id():  # noqa: E501
    article = _make_article()
    same_t = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    later = same_t + timedelta(seconds=5)
    history = [
        _msg(id=20, role="assistant", content="z", created_at=later),
        _msg(id=11, role="assistant", content="b", created_at=same_t),
        _msg(id=10, role="user", content="a", created_at=same_t),
    ]
    msgs = build_chat_messages(article, None, history, "q", history_window=10)
    contents = [m["content"] for m in msgs[1:-1]]
    assert contents == ["a", "b", "z"]


def test_prompt_builder_excludes_assistant_rows_with_is_error_true_from_history():
    article = _make_article()
    history = [
        _msg(
            id=1,
            role="user",
            content="u1",
            created_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        ),
        _msg(
            id=2,
            role="assistant",
            content="ERR",
            is_error=True,
            created_at=datetime(2026, 5, 1, 12, 1, tzinfo=UTC),
        ),
        _msg(
            id=3,
            role="assistant",
            content="a1",
            created_at=datetime(2026, 5, 1, 12, 2, tzinfo=UTC),
        ),
    ]
    msgs = build_chat_messages(article, None, history, "q", history_window=10)
    contents = [m["content"] for m in msgs[1:-1]]
    assert "ERR" not in contents
    assert contents == ["u1", "a1"]


def test_prompt_builder_caps_history_at_chat_history_window_most_recent():
    article = _make_article()
    base = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    history = [
        _msg(
            id=i,
            role="user" if i % 2 == 0 else "assistant",
            content=f"m{i}",
            created_at=base + timedelta(seconds=i),
        )
        for i in range(20)
    ]
    msgs = build_chat_messages(article, None, history, "q", history_window=5)
    contents = [m["content"] for m in msgs[1:-1]]
    assert contents == ["m15", "m16", "m17", "m18", "m19"]


def test_prompt_builder_does_not_double_count_new_user_message_when_already_in_history():  # noqa: E501
    article = _make_article()
    base = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    history = [
        _msg(id=1, role="user", content="prior", created_at=base),
        _msg(
            id=2,
            role="assistant",
            content="prior reply",
            created_at=base + timedelta(seconds=1),
        ),
        _msg(
            id=3, role="user", content="new q", created_at=base + timedelta(seconds=2)
        ),
    ]
    msgs = build_chat_messages(article, None, history, "new q", history_window=10)
    user_contents = [m["content"] for m in msgs if m["role"] == "user"]
    assert user_contents.count("new q") == 1
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"] == "new q"


# ---------------------------------------------------------------------------
# Mock-mode path
# ---------------------------------------------------------------------------


async def test_mock_mode_dispatches_to_chat_mock_generator_token_stream(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", True)
    session = _make_read_session()

    chunks = [c async for c in token_stream(session, 1, "hi")]

    assert "".join(chunks) == MOCK_REPLY


async def test_mock_mode_does_not_instantiate_async_openai_client(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", True)
    session = _make_read_session()
    cls, _ = _make_async_openai(_FakeStream([]))

    with patch("openai.AsyncOpenAI", cls):
        async for _ in token_stream(session, 1, "hi"):
            pass

    cls.assert_not_called()


async def test_mock_mode_makes_no_call_to_chat_completions_create(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", True)
    session = _make_read_session()
    cls, create_mock = _make_async_openai(_FakeStream([]))

    with patch("openai.AsyncOpenAI", cls):
        async for _ in token_stream(session, 1, "hi"):
            pass

    create_mock.assert_not_called()


async def test_mock_mode_works_with_placeholder_openai_api_key(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", True)
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-placeholder")
    session = _make_read_session()

    chunks = [c async for c in token_stream(session, 1, "hi")]

    assert "".join(chunks) == MOCK_REPLY


# ---------------------------------------------------------------------------
# Failure path — _stream_real_llm propagation
# ---------------------------------------------------------------------------


async def test_real_path_raises_on_timeout_so_streaming_service_can_persist_sentinel(
    monkeypatch,
):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    cls, _ = _make_async_openai(TimeoutError("timed out"))

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(TimeoutError):
            async for _ in chat_llm._stream_real_llm([]):
                pass


async def test_real_path_raises_on_openai_api_error(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)

    class FakeAPIError(Exception):
        pass

    cls, _ = _make_async_openai(FakeAPIError("rate limited"))

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(FakeAPIError):
            async for _ in chat_llm._stream_real_llm([]):
                pass


async def test_real_path_raises_on_connection_error(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    cls, _ = _make_async_openai(ConnectionError("dns fail"))

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(ConnectionError):
            async for _ in chat_llm._stream_real_llm([]):
                pass


async def test_real_path_raises_on_mid_stream_exception_after_partial_tokens(
    monkeypatch,
):
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    fake_stream = _FakeStream(["a", "b", "c"]).with_exception_at(
        2, RuntimeError("boom")
    )
    cls, _ = _make_async_openai(fake_stream)

    yielded: list[str] = []
    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(RuntimeError):
            async for c in chat_llm._stream_real_llm([]):
                yielded.append(c)

    assert yielded == ["a", "b"]


# ---------------------------------------------------------------------------
# Failure path — streaming-service end-to-end (real LLM mocked)
# ---------------------------------------------------------------------------


def _make_request_session(*, article_id_returned: int | None):
    session = AsyncMock()
    session.scalar.return_value = article_id_returned
    session.add = MagicMock()
    return session


def _make_assistant_session_factory(
    *,
    article: Article | None = None,
    fake: ArticleFake | None = None,
    history_rows: list[ChatMessage] | None = None,
):
    """Same shape as test_chat_service's helper; returns (factory, captured)
    where captured serves both the chat_llm read_session and the assistant
    write."""
    captured = AsyncMock()
    captured.add = MagicMock()
    captured.get = AsyncMock(
        return_value=article if article is not None else _make_article()
    )
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=fake)
    history_result = MagicMock()
    rows_desc = sorted(
        history_rows or [], key=lambda r: (r.created_at, r.id), reverse=True
    )
    history_result.scalars.return_value.all.return_value = rows_desc
    captured.execute = AsyncMock(side_effect=[fake_result, history_result])
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=captured)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=cm)
    return factory, captured


async def _drive_real_path_with_stream(
    deltas: list[str | None],
    *,
    raise_at: int | None = None,
    raise_with: BaseException | None = None,
    message: str = "hi",
    factory_kwargs: dict | None = None,
) -> tuple[bytes, MagicMock]:
    """Drive post_chat_stream end-to-end with chat_llm_mock=False, the
    OpenAI SDK patched to a fake stream. Returns (body_bytes, captured)."""
    request_session = _make_request_session(article_id_returned=1)
    factory, captured = _make_assistant_session_factory(**(factory_kwargs or {}))
    fake_stream = _FakeStream(list(deltas))
    if raise_at is not None:
        fake_stream.with_exception_at(raise_at, raise_with or RuntimeError("boom"))
    cls, _ = _make_async_openai(fake_stream)

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch("openai.AsyncOpenAI", cls),
        patch.object(settings, "chat_llm_mock", False),
    ):
        response = await post_chat_stream(
            request_session, 1, ChatPostRequest(message=message)
        )
        body = b"".join([chunk async for chunk in response.body_iterator])
    return body, captured


async def test_streaming_endpoint_commits_user_row_before_first_token_event_real_path():
    request_session = _make_request_session(article_id_returned=1)
    factory, captured = _make_assistant_session_factory()
    fake_stream = _FakeStream(["alpha", "beta"])
    cls, _ = _make_async_openai(fake_stream)

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch("openai.AsyncOpenAI", cls),
        patch.object(settings, "chat_llm_mock", False),
    ):
        response = await post_chat_stream(
            request_session, 1, ChatPostRequest(message="hi")
        )
        request_session.flush.assert_awaited_once()
        request_session.commit.assert_awaited_once()
        assert request_session.add.call_count == 1
        user_row = request_session.add.call_args.args[0]
        assert user_row.role == "user"
        assert user_row.is_error is False
        body = b"".join([chunk async for chunk in response.body_iterator])

    assert b'"token"' in body


async def test_streaming_endpoint_commits_assistant_row_before_done_terminator_real_path():  # noqa: E501
    body, captured = await _drive_real_path_with_stream(["Hello, ", "world", "."])

    assert b"data: [DONE]\n\n" in body
    done_index = body.index(b"data: [DONE]\n\n")
    assistant_row = captured.add.call_args.args[0]
    assert assistant_row.role == "assistant"
    assert assistant_row.is_error is False
    assert assistant_row.content == "Hello, world."
    captured.commit.assert_awaited_once()
    assert done_index > 0


async def test_streaming_endpoint_persists_assistant_row_with_sentinel_content_on_real_failure():  # noqa: E501
    body, captured = await _drive_real_path_with_stream(
        ["a", "b", "c"], raise_at=1, raise_with=RuntimeError("mid-stream")
    )

    assert captured.add.call_count == 1
    row = captured.add.call_args.args[0]
    assert row.is_error is True
    assert row.content == STREAM_FAILURE_SENTINEL


async def test_streaming_endpoint_emits_single_error_event_with_sentinel_on_real_failure():  # noqa: E501
    body, _ = await _drive_real_path_with_stream(
        ["a", "b"], raise_at=1, raise_with=TimeoutError("t")
    )

    assert body.count(b'"error"') == 1
    assert STREAM_FAILURE_SENTINEL.encode() in body


async def test_streaming_endpoint_does_not_emit_done_after_real_failure():
    body, _ = await _drive_real_path_with_stream(
        ["a"], raise_at=0, raise_with=RuntimeError("nope")
    )

    assert b"[DONE]" not in body


async def test_streaming_endpoint_returns_200_and_does_not_raise_on_real_failure():
    request_session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()
    fake_stream = _FakeStream(["a"]).with_exception_at(0, RuntimeError("nope"))
    cls, _ = _make_async_openai(fake_stream)

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch("openai.AsyncOpenAI", cls),
        patch.object(settings, "chat_llm_mock", False),
    ):
        response = await post_chat_stream(
            request_session, 1, ChatPostRequest(message="hi")
        )
        # consume body without raising
        body = b"".join([c async for c in response.body_iterator])

    assert response.status_code == 200
    assert b'"error"' in body


async def test_streaming_endpoint_logs_one_error_with_article_id_and_exc_type_name_on_real_failure(  # noqa: E501
    caplog,
):
    request_session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()
    fake_stream = _FakeStream(["a"]).with_exception_at(0, TimeoutError("t"))
    cls, _ = _make_async_openai(fake_stream)

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch("openai.AsyncOpenAI", cls),
        patch.object(settings, "chat_llm_mock", False),
        caplog.at_level(logging.ERROR, logger="app.services.chat"),
    ):
        response = await post_chat_stream(
            request_session, 1, ChatPostRequest(message="hi")
        )
        async for _ in response.body_iterator:
            pass

    error_records = [
        r
        for r in caplog.records
        if r.name == "app.services.chat" and r.levelno >= logging.ERROR
    ]
    assert len(error_records) == 1
    msg = error_records[0].getMessage()
    assert "article_id=1" in msg
    assert "TimeoutError" in msg


async def test_real_failure_after_partial_tokens_persisted_assistant_content_is_sentinel_only():  # noqa: E501
    body, captured = await _drive_real_path_with_stream(
        ["alpha", "beta", "gamma"], raise_at=2, raise_with=RuntimeError("late")
    )

    row = captured.add.call_args.args[0]
    assert row.content == STREAM_FAILURE_SENTINEL
    # tokens that were already emitted are not reconstructable from the row
    assert "alpha" not in row.content
    assert "beta" not in row.content


# ---------------------------------------------------------------------------
# Public router contract non-regression
# ---------------------------------------------------------------------------


async def test_public_router_post_chat_url_status_codes_and_sse_format_unchanged_from_task_1(  # noqa: E501
    client,
):
    # Mock-mode happy path: same wire shape Task 1 shipped (200 + SSE events).
    # We patch the streaming-service's session factory so neither a real DB
    # nor the request-side article check is required, and assert framing.
    request_factory, captured = _make_assistant_session_factory()

    async def fake_get_session():
        s = AsyncMock()
        s.scalar.return_value = 1
        s.add = MagicMock()
        yield s

    from app.db import get_session

    client._transport.app.dependency_overrides[get_session] = fake_get_session
    try:
        with patch("app.services.chat.AsyncSessionLocal", request_factory):
            async with client.stream(
                "POST",
                "/api/articles/1/chat",
                json={"message": "hi"},
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers["content-type"]
                body = b""
                async for chunk in resp.aiter_bytes():
                    body += chunk
        assert b"data: " in body
        assert b"[DONE]" in body
    finally:
        client._transport.app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------------------
# Logging / safety
# ---------------------------------------------------------------------------


async def test_no_log_record_emitted_during_real_streaming_contains_user_message_or_prompt_or_response_or_api_key(  # noqa: E501
    caplog, monkeypatch
):
    monkeypatch.setattr(settings, "openai_api_key", "sk-secret-do-not-leak")
    monkeypatch.setattr(settings, "chat_llm_mock", False)
    secret_user_message = "USER-MSG-DO-NOT-LEAK"
    secret_chunk = "RESPONSE-CHUNK-DO-NOT-LEAK"
    fake_stream = _FakeStream([secret_chunk])
    cls, _ = _make_async_openai(fake_stream)
    request_session = _make_request_session(article_id_returned=1)
    factory, _ = _make_assistant_session_factory()

    with (
        patch("app.services.chat.AsyncSessionLocal", factory),
        patch("openai.AsyncOpenAI", cls),
        caplog.at_level(logging.DEBUG),
    ):
        response = await post_chat_stream(
            request_session, 1, ChatPostRequest(message=secret_user_message)
        )
        async for _ in response.body_iterator:
            pass

    for record in caplog.records:
        msg = record.getMessage()
        assert secret_user_message not in msg
        assert secret_chunk not in msg
        assert "sk-secret-do-not-leak" not in msg
        # Fragment of the system prompt the chat_llm module owns:
        assert "context-aware assistant" not in msg


def test_stream_failure_sentinel_is_short_human_readable_and_does_not_contain_provider_details():  # noqa: E501
    s = STREAM_FAILURE_SENTINEL
    assert isinstance(s, str)
    assert 0 < len(s) <= 80
    assert s == s.strip()
    assert all(0x20 <= ord(c) < 0x7F for c in s), "must be ASCII-printable"
    lower = s.lower()
    assert "openai" not in lower
    assert "api" not in lower
    assert "401" not in s and "429" not in s and "500" not in s
    assert "traceback" not in lower


# ---------------------------------------------------------------------------
# token_stream — article presence check
# ---------------------------------------------------------------------------


async def test_token_stream_raises_not_found_when_article_missing(monkeypatch):
    monkeypatch.setattr(settings, "chat_llm_mock", True)
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        async for _ in token_stream(session, 999, "hi"):
            pass


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_chat_llm_module_exposes_required_public_symbols():
    assert isinstance(SYSTEM_PROMPT, str) and SYSTEM_PROMPT
    assert isinstance(STREAM_FAILURE_SENTINEL, str) and STREAM_FAILURE_SENTINEL
    assert callable(build_chat_messages)
    assert callable(token_stream)
