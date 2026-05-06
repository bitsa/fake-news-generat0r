import asyncio

from fastapi import APIRouter, Response

from app.db import check_db
from app.redis_client import check_redis
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    db_ok, redis_ok = await asyncio.gather(check_db(), check_redis())
    healthy = db_ok and redis_ok
    response.status_code = 200 if healthy else 503
    return HealthResponse(status="ok" if healthy else "error")
