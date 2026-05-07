from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.chat import ChatHistoryResponse
from app.services import chat as chat_service

router = APIRouter(prefix="/api")


@router.get("/articles/{article_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(
    article_id: int,
    session: AsyncSession = Depends(get_session),
) -> ChatHistoryResponse:
    return await chat_service.get_chat_history(session, article_id)
