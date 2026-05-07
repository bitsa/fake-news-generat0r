import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from arq import cron

from app.services.scraper import IngestResult
from app.workers.transform import WorkerSettings, scheduled_scrape


@pytest.mark.asyncio
async def test_scheduled_scrape_invokes_scrape_cycle_with_ctx_redis():
    redis_pool = MagicMock(name="ArqRedis")
    ctx = {"redis": redis_pool}
    fake_result = IngestResult(inserted=[], fetched=0)

    with patch(
        "app.workers.transform.scraper.scrape_cycle",
        new=AsyncMock(return_value=fake_result),
    ) as mock_cycle:
        await scheduled_scrape(ctx)

    mock_cycle.assert_awaited_once_with(redis_pool)


@pytest.mark.asyncio
async def test_scheduled_scrape_swallows_exceptions(caplog):
    ctx = {"redis": MagicMock(name="ArqRedis")}

    with patch(
        "app.workers.transform.scraper.scrape_cycle",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with caplog.at_level(logging.WARNING, logger="app.workers.transform"):
            await scheduled_scrape(ctx)

    assert any("worker.cron.scrape.failed" in r.message for r in caplog.records)


def test_worker_settings_registers_cron_at_zero_and_thirty():
    cron_jobs = WorkerSettings.cron_jobs
    assert len(cron_jobs) == 1
    job = cron_jobs[0]
    assert job.coroutine is scheduled_scrape
    assert job.minute == {0, 30}
    assert job.run_at_startup is False


def test_worker_settings_cron_helper_signature_matches():
    # Sanity: rebuild the same cron entry to confirm we're using the public API
    rebuilt = cron(scheduled_scrape, minute={0, 30}, run_at_startup=False)
    assert rebuilt.coroutine is scheduled_scrape
    assert rebuilt.minute == {0, 30}
