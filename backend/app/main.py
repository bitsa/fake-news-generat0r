import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import AppError
from app.logging_config import configure_logging
from app.redis_client import close_redis
from app.routers import health

configure_logging()


async def _run_migrations() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    await asyncio.to_thread(alembic_upgrade, cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _run_migrations()
    yield
    await close_redis()


app = FastAPI(title="fake-news-generator", lifespan=lifespan)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


app.include_router(health.router)
