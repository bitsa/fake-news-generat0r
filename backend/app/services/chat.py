import json
import logging
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.exceptions import NotFoundError, ValidationError
from app.models import Article, ChatMessage
from app.schemas.chat import ChatHistoryResponse, ChatMessageOut, ChatPostRequest
from app.services.chat_generator import ERROR_SENTINEL, stream_mock_reply
from app.services.sanitize import clean_text

# NOTE: clean_text() is best-effort sanitization (HTML-decode, tag-strip,
# whitespace-collapse) reused from the article ingest pipeline. It is *not*
# sufficient as a real guardrail for user-provided LLM input. Before any
# untrusted-traffic shipping we still need: prompt-injection defences,
# max-token-budget enforcement on the model side, an allow-list of
# permitted character classes / unicode ranges, content-policy / abuse
# filtering, and per-article rate limiting. Wired in here so we both
# avoid persisting raw HTML / tag soup in chat_messages and avoid
# forwarding obviously-malformed payloads to the LLM call site.

log = logging.getLogger(__name__)


_SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _sse_token(chunk: str) -> bytes:
    return f"data: {json.dumps({'token': chunk}, ensure_ascii=False)}\n\n".encode()


def _sse_done() -> bytes:
    return b"data: [DONE]\n\n"


def _sse_error(message: str) -> bytes:
    return f"data: {json.dumps({'error': message}, ensure_ascii=False)}\n\n".encode()


async def get_chat_history(
    session: AsyncSession, article_id: int
) -> ChatHistoryResponse:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.article_id == article_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    rows = result.scalars().all()

    if not rows:
        article_exists = await session.scalar(
            select(Article.id).where(Article.id == article_id)
        )
        if article_exists is None:
            raise NotFoundError(f"Article {article_id} not found")

    messages = [ChatMessageOut.model_validate(row) for row in rows]
    log.info("chat.history.get article_id=%d count=%d", article_id, len(messages))
    return ChatHistoryResponse(article_id=article_id, messages=messages)


async def post_chat_stream(
    session: AsyncSession,
    article_id: int,
    body: ChatPostRequest,
) -> StreamingResponse:
    article_exists = await session.scalar(
        select(Article.id).where(Article.id == article_id)
    )
    if article_exists is None:
        raise NotFoundError(f"Article {article_id} not found")

    sanitized = clean_text(body.message)
    if not sanitized:
        raise ValidationError("message is empty after sanitization")

    user_row = ChatMessage(
        article_id=article_id,
        role="user",
        content=sanitized,
        is_error=False,
    )
    session.add(user_row)
    await session.flush()
    await session.commit()

    log.info("chat.post.begin article_id=%d msg_len=%d", article_id, len(sanitized))

    return StreamingResponse(
        _stream_assistant(article_id, sanitized),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _stream_assistant(article_id: int, message: str) -> AsyncIterator[bytes]:
    tokens: list[str] = []
    try:
        async for chunk in stream_mock_reply(message):
            tokens.append(chunk)
            yield _sse_token(chunk)
    except Exception as exc:
        log.error(
            "chat.stream.error article_id=%d exc_type=%s",
            article_id,
            type(exc).__name__,
        )
        async with AsyncSessionLocal() as assistant_session:
            assistant_session.add(
                ChatMessage(
                    article_id=article_id,
                    role="assistant",
                    content=ERROR_SENTINEL,
                    is_error=True,
                )
            )
            await assistant_session.commit()
        yield _sse_error(ERROR_SENTINEL)
        return

    async with AsyncSessionLocal() as assistant_session:
        assistant_session.add(
            ChatMessage(
                article_id=article_id,
                role="assistant",
                content="".join(tokens),
                is_error=False,
            )
        )
        await assistant_session.commit()
    log.info("chat.post.complete article_id=%d tokens=%d", article_id, len(tokens))
    yield _sse_done()
