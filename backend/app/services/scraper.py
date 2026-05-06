import logging
import time
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
    log.info("scraper.fetch.begin source=%s", source)
    started = time.perf_counter()
    async with httpx.AsyncClient() as client:
        response = await client.get(FEED_URLS[source])
        response.raise_for_status()
    feed = feedparser.parse(response.text)
    entries = feed.entries[: settings.scrape_max_per_source]
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log.info(
        "scraper.fetch.ok source=%s entries=%d elapsed_ms=%d",
        source,
        len(entries),
        elapsed_ms,
    )
    return entries


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
    sources = list(Source)
    log.info("scraper.ingest.begin sources=%d", len(sources))
    all_inserted: list[Article] = []
    total_fetched: int = 0
    failed: int = 0

    for source in sources:
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

            total_fetched += len(raw_entries)
            source_inserted: list[Article] = []

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
                source_inserted = list(result.scalars().all())
                all_inserted.extend(source_inserted)

            await session.commit()
            log.info(
                "scraper.source.ok source=%s fetched=%d inserted=%d",
                source,
                len(raw_entries),
                len(source_inserted),
            )

        except Exception:
            await session.rollback()
            log.warning("scraper.source.failed source=%s", source, exc_info=True)
            failed += 1
            continue

    if failed == len(sources):
        raise ServiceUnavailableError("All RSS sources failed")

    log.info(
        "scraper.ingest.complete fetched=%d inserted=%d failed=%d",
        total_fetched,
        len(all_inserted),
        failed,
    )
    return IngestResult(inserted=all_inserted, fetched=total_fetched)
