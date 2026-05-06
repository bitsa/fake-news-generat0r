import asyncio
import logging

from redis.asyncio import Redis

from app.config import settings

log = logging.getLogger(__name__)

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def check_redis() -> bool:
    try:
        await asyncio.wait_for(get_redis().ping(), timeout=2.0)
        return True
    except Exception as e:
        log.warning("health.redis.unavailable error_type=%s", e.__class__.__name__)
        return False
