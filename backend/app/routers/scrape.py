from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services import scraper

router = APIRouter(prefix="/api")


@router.post("/scrape", status_code=202)
async def scrape(session: AsyncSession = Depends(get_session)) -> dict:
    result = await scraper.ingest_all(session)
    return {"inserted": len(result.inserted), "fetched": result.fetched}
