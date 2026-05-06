import logging

import sqlalchemy as sa
from arq.connections import RedisSettings

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Article, ArticleFake
from app.services import openai_transform

log = logging.getLogger(__name__)


async def transform_article(ctx: dict, article_id: int) -> None:
    log.info("worker.transform.start article_id=%d", article_id)
    async with AsyncSessionLocal() as session:
        fake = await session.get(ArticleFake, article_id)
        if fake is None:
            log.info("worker.transform.skip.missing article_id=%d", article_id)
            return
        if fake.transform_status == "completed":
            log.info("worker.transform.skip.completed article_id=%d", article_id)
            return
        article = await session.get(Article, article_id)
        if article is None:
            log.info("worker.transform.skip.no_article article_id=%d", article_id)
            return
        try:
            pair = await openai_transform.generate_satirical(
                article.title, article.description
            )
            fake.title = pair.title
            fake.description = pair.description
            fake.model = settings.openai_model_transform
            fake.temperature = settings.openai_temperature_transform
            fake.transform_status = "completed"
            await session.commit()
            log.info(
                "worker.transform.done article_id=%d model=%s",
                article_id,
                settings.openai_model_transform,
            )
        except Exception as exc:
            await session.rollback()
            await session.execute(
                sa.delete(ArticleFake).where(ArticleFake.article_id == article_id)
            )
            await session.commit()
            log.error(
                "worker.transform.failed article_id=%d exc_type=%s",
                article_id,
                type(exc).__name__,
            )


class WorkerSettings:
    functions = [transform_article]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 1
