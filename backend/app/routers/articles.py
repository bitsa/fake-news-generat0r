from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.articles import ArticlesResponse
from app.services import articles as articles_service

router = APIRouter(prefix="/api")


@router.get("/articles", response_model=ArticlesResponse)
async def get_articles(
    session: AsyncSession = Depends(get_session),
) -> ArticlesResponse:
    return await articles_service.get_articles(session)
