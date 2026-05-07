from arq.connections import ArqRedis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.arq_client import get_arq_pool
from app.db import get_session
from app.schemas.scrape import ScrapeResponse
from app.services import scraper, transformer

router = APIRouter(prefix="/api")


@router.post("/scrape", status_code=202, response_model=ScrapeResponse)
async def scrape(
    session: AsyncSession = Depends(get_session),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> ScrapeResponse:
    result = await scraper.ingest_all(session)
    await transformer.create_and_enqueue(session, arq_pool, result.inserted)
    return ScrapeResponse(
        inserted=len(result.inserted),
        fetched=result.fetched,
        skipped_url_duplicates=result.skipped_url_duplicates,
        skipped_near_duplicates=result.skipped_near_duplicates,
        embedding_calls=result.embedding_calls,
    )
