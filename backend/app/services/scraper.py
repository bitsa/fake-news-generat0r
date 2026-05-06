import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import ServiceUnavailableError
from app.models import Article
from app.sources import FEED_URLS, Source

log = logging.getLogger(__name__)

type RawEntry = Any


@dataclass
class IngestResult:
    inserted: list[Article]
    fetched: int


async def fetch_feed(source: Source) -> list[RawEntry]:
    async with httpx.AsyncClient() as client:
        response = await client.get(FEED_URLS[source])
        response.raise_for_status()
    feed = feedparser.parse(response.text)
    return feed.entries[: settings.scrape_max_per_source]


def parse_entry(entry: RawEntry, source: Source) -> Article | None:
    title = (entry.get("title") or "").strip()
    url = (entry.get("link") or "").strip()
    description = (entry.get("summary") or "").strip()

    if not title or not url or not description:
        return None

    published_parsed = entry.get("published_parsed")
    published_at: datetime | None = None
    if published_parsed is not None:
        published_at = datetime(*published_parsed[:6], tzinfo=UTC)

    return Article(
        source=source,
        title=title,
        url=url,
        description=description,
        published_at=published_at,
    )


async def ingest_all(session: AsyncSession) -> IngestResult:
    all_inserted: list[Article] = []
    total_fetched: int = 0
    failed: int = 0

    for source in Source:
        try:
            raw_entries = await fetch_feed(source)
            valid_articles: list[Article] = []
            for entry in raw_entries:
                article = parse_entry(entry, source)
                if article is None:
                    log.warning(
                        "scraper.entry.dropped source=%s url=%s",
                        source,
                        entry.get("link"),
                    )
                    continue
                valid_articles.append(article)

            total_fetched += len(valid_articles)

            if valid_articles:
                stmt = (
                    pg_insert(Article)
                    .values(
                        [
                            {
                                "source": a.source,
                                "title": a.title,
                                "url": a.url,
                                "description": a.description,
                                "published_at": a.published_at,
                            }
                            for a in valid_articles
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=["url"])
                    .returning(Article)
                )
                result = await session.execute(stmt)
                all_inserted.extend(result.scalars().all())

            await session.commit()

        except Exception:
            log.warning("scraper.source.failed source=%s", source, exc_info=True)
            failed += 1
            continue

    if failed == len(list(Source)):
        raise ServiceUnavailableError("All RSS sources failed")

    return IngestResult(inserted=all_inserted, fetched=total_fetched)
