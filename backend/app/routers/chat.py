from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.chat import ChatHistoryResponse, ChatPostRequest
from app.services import chat as chat_service

router = APIRouter(prefix="/api")


@router.get("/articles/{article_id}/chat", response_model=ChatHistoryResponse)
async def get_chat_history(
    article_id: int,
    session: AsyncSession = Depends(get_session),
) -> ChatHistoryResponse:
    return await chat_service.get_chat_history(session, article_id)


@router.post("/articles/{article_id}/chat")
async def post_chat(
    article_id: int,
    body: ChatPostRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    return await chat_service.post_chat_stream(session, article_id, body)
