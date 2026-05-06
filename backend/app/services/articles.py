import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleFake
from app.schemas.articles import (
    ArticleOut,
    ArticlePairOut,
    ArticlesResponse,
    FakeOut,
)

log = logging.getLogger(__name__)


async def get_articles(session: AsyncSession) -> ArticlesResponse:
    total = (await session.scalar(select(func.count()).select_from(Article))) or 0

    pending = (
        await session.scalar(
            select(func.count())
            .select_from(ArticleFake)
            .where(ArticleFake.transform_status == "pending")
        )
    ) or 0

    result = await session.execute(
        select(Article, ArticleFake)
        .join(ArticleFake, Article.id == ArticleFake.article_id)
        .where(ArticleFake.transform_status == "completed")
        .order_by(Article.published_at.desc().nullslast())
    )
    rows = result.all()

    pairs = [
        ArticlePairOut(
            id=article.id,
            article=ArticleOut.model_validate(article),
            fake=FakeOut.model_validate(fake),
        )
        for article, fake in rows
    ]

    log.info(
        "articles.get total=%d pending=%d completed=%d",
        total,
        pending,
        len(pairs),
    )

    return ArticlesResponse(total=total, pending=pending, articles=pairs)
