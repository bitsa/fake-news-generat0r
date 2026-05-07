import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models import Article, ChatMessage
from app.schemas.chat import ChatHistoryResponse, ChatMessageOut

log = logging.getLogger(__name__)


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
