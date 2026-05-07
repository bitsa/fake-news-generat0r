import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import arq_client
from app.db import AsyncSessionLocal
from app.exceptions import AppError
from app.logging_config import configure_logging
from app.redis_client import close_redis
from app.routers import articles, chat, health, scrape
from app.services import scraper, transformer

configure_logging()

log = logging.getLogger(__name__)


async def _run_migrations() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    await asyncio.to_thread(alembic_upgrade, cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup.migrations.begin")
    await _run_migrations()
    configure_logging()
    log.info("startup.migrations.complete")
    app.state.arq_pool = await arq_client.create_arq_pool()
    try:
        log.info("startup.scrape.begin")
        async with AsyncSessionLocal() as session:
            await transformer.recover_stale_pending(session, app.state.arq_pool)
            result = await scraper.ingest_all(session)
            await transformer.create_and_enqueue(
                session, app.state.arq_pool, result.inserted
            )
        log.info("startup.scrape.complete")
    except Exception:
        log.warning("startup.scrape.failed", exc_info=True)
    yield
    await arq_client.close_arq_pool(app.state.arq_pool)
    await close_redis()


app = FastAPI(title="fake-news-generator", lifespan=lifespan)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


app.include_router(health.router)
app.include_router(scrape.router)
app.include_router(articles.router)
app.include_router(chat.router)
