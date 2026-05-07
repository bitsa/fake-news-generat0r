import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import feedparser
import httpx
from arq.connections import ArqRedis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import AsyncSessionLocal
from app.exceptions import ServiceUnavailableError
from app.models import Article, ArticleEmbedding
from app.services import transformer
from app.services.dedup import (
    Incumbent,
    find_near_duplicate,
    tokenize,
)
from app.services.sanitize import clean_text
from app.sources import FEED_URLS, Source

log = logging.getLogger(__name__)

type RawEntry = Any


@dataclass
class IngestResult:
    inserted: list[Article] = field(default_factory=list)
    fetched: int = 0
    skipped_url_duplicates: int = 0
    skipped_near_duplicates: int = 0
    embedding_calls: int = 0


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
    title = clean_text(entry.get("title") or "")
    url = (entry.get("link") or "").strip()
    description = clean_text(entry.get("summary") or "")

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


async def _load_incumbents(session: AsyncSession) -> list[Incumbent]:
    stmt = text("""
        SELECT a.id, a.title, a.description, ae.embedding
          FROM articles a
          LEFT JOIN article_embeddings ae ON ae.article_id = a.id
         WHERE COALESCE(a.published_at, a.created_at)
               > now() - make_interval(hours => :hours)
        """)
    rows = await session.execute(stmt, {"hours": settings.dedup_window_hours})
    incumbents: list[Incumbent] = []
    for row in rows:
        article_id, title, description, embedding = row
        emb_list: list[float] | None
        if embedding is None:
            emb_list = None
        else:
            emb_list = list(embedding)
        incumbents.append(
            Incumbent(
                article_id=article_id,
                tokens=tokenize(title or ""),
                text=f"{title or ''}\n\n{description or ''}",
                embedding=emb_list,
            )
        )
    return incumbents


async def _url_exists(session: AsyncSession, url: str) -> bool:
    existing_id = await session.scalar(select(Article.id).where(Article.url == url))
    return existing_id is not None


async def ingest_all(session: AsyncSession) -> IngestResult:
    sources = list(Source)
    log.info("scraper.ingest.begin sources=%d", len(sources))
    result = IngestResult()
    failed = 0

    incumbents = await _load_incumbents(session)

    for source in sources:
        try:
            raw_entries = await fetch_feed(source)
            result.fetched += len(raw_entries)

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

            source_inserted: list[Article] = []
            for cand in valid_articles:
                if await _url_exists(session, cand.url):
                    result.skipped_url_duplicates += 1
                    log.debug(
                        "scraper.entry.duplicate source=%s url=%s",
                        source,
                        cand.url,
                    )
                    continue

                cand_text = f"{cand.title}\n\n{cand.description}"
                decision = await find_near_duplicate(
                    session, cand.title, cand_text, incumbents
                )
                result.embedding_calls += decision.embedding_calls

                if not decision.accept:
                    result.skipped_near_duplicates += 1
                    log.info(
                        "scraper.dedup.skip reason=%s candidate_url=%s "
                        "matched_article_id=%s",
                        decision.reason,
                        cand.url,
                        decision.matched_article_id,
                    )
                    await session.commit()
                    continue

                session.add(cand)
                await session.flush()
                if decision.candidate_embedding is not None:
                    session.add(
                        ArticleEmbedding(
                            article_id=cand.id,
                            embedding=decision.candidate_embedding,
                            model=settings.openai_model_embedding,
                        )
                    )
                await session.commit()
                source_inserted.append(cand)
                incumbents.append(
                    Incumbent(
                        article_id=cand.id,
                        tokens=tokenize(cand.title),
                        text=cand_text,
                        embedding=decision.candidate_embedding,
                    )
                )

            result.inserted.extend(source_inserted)
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
        "scraper.ingest.complete fetched=%d inserted=%d "
        "skipped_url=%d skipped_near=%d embed_calls=%d failed=%d",
        result.fetched,
        len(result.inserted),
        result.skipped_url_duplicates,
        result.skipped_near_duplicates,
        result.embedding_calls,
        failed,
    )
    return result


async def scrape_cycle(arq_pool: ArqRedis) -> IngestResult:
    async with AsyncSessionLocal() as session:
        result = await ingest_all(session)
        await transformer.create_and_enqueue(session, arq_pool, result.inserted)
    return result
