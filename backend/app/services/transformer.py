import logging
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Article, ArticleFake

log = logging.getLogger(__name__)


async def create_and_enqueue(
    session: AsyncSession,
    arq_pool: ArqRedis,
    articles: list[Article],
) -> None:
    if not articles:
        return

    session.add_all([ArticleFake(article_id=a.id) for a in articles])
    await session.commit()

    for article in articles:
        try:
            await arq_pool.enqueue_job("transform_article", article.id)
        except Exception:
            log.warning(
                "transformer.enqueue.failed article_id=%d",
                article.id,
                exc_info=True,
            )


async def recover_stale_pending(
    session: AsyncSession,
    arq_pool: ArqRedis,
) -> int:
    stale_threshold = datetime.now(UTC) - timedelta(
        minutes=settings.transform_recovery_threshold_minutes
    )
    result = await session.execute(
        sa.select(ArticleFake.article_id).where(
            ArticleFake.transform_status == "pending",
            ArticleFake.created_at < stale_threshold,
        )
    )
    article_ids = result.scalars().all()

    count = 0
    for article_id in article_ids:
        try:
            await arq_pool.enqueue_job("transform_article", article_id)
            count += 1
        except Exception:
            log.warning(
                "transformer.recover.enqueue.failed article_id=%d",
                article_id,
                exc_info=True,
            )

    return count
