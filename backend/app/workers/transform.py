import logging

import sqlalchemy as sa
from arq.connections import RedisSettings

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import ArticleFake

log = logging.getLogger(__name__)

MOCK_TITLE: str = "Local Man Discovers He's Been Doing Everything Wrong This Whole Time"
MOCK_DESCRIPTION: str = (
    "Experts confirm the situation is exactly as bad as it sounds, "
    "but stress there is still time to feel vaguely embarrassed about it."
)


async def transform_article(ctx: dict, article_id: int) -> None:
    log.info("worker.transform.start article_id=%d", article_id)
    async with AsyncSessionLocal() as session:
        fake = await session.get(ArticleFake, article_id)
        if fake is None:
            log.info("worker.transform.skip article_id=%d", article_id)
            return
        try:
            fake.title = MOCK_TITLE
            fake.description = MOCK_DESCRIPTION
            fake.model = settings.openai_model_transform
            fake.temperature = settings.openai_temperature_transform
            fake.transform_status = "completed"
            await session.commit()
            log.info("worker.transform.done article_id=%d", article_id)
        except Exception:
            await session.rollback()
            await session.execute(
                sa.delete(ArticleFake).where(ArticleFake.article_id == article_id)
            )
            await session.commit()
            log.error(
                "worker.transform.failed article_id=%d", article_id, exc_info=True
            )


class WorkerSettings:
    functions = [transform_article]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 1
