# RSS Scraper — QA Audit

**Task:** rss-scraper
**Spec:** [rss-scraper-spec.md](rss-scraper-spec.md)
**Test files audited:**

- `backend/tests/unit/test_scraper.py`
- `backend/tests/routers/test_scrape.py`

---

## Coverage Map

| # | Acceptance Criterion (summary) | Test file | Test function(s) |
|---|---|---|---|
| 1 | Lifespan calls `ingest_all` after `_run_migrations`; app starts even on partial ingest failure | `test_scrape.py` | `test_lifespan_calls_ingest_all_after_migrations` |
| 2 | `fetch_feed` uses `httpx`, passes `response.text` to `feedparser.parse()`, never uses feedparser's own network fetch | `test_scraper.py` | `test_fetch_feed_passes_response_text_to_feedparser`, `test_fetch_feed_caps_at_scrape_max_per_source` |
| 3 | `fetch_feed` caps results at `settings.scrape_max_per_source`; setting is read from `Settings` | `test_scraper.py` | `test_fetch_feed_caps_at_scrape_max_per_source` |
| 4 | `parse_entry` returns `Article` for valid entry; returns `None` for missing/blank title, URL, or description; caller logs exactly one `WARNING` per `None` | `test_scraper.py` | `test_parse_entry_returns_article_for_valid_entry`, `test_parse_entry_returns_none_for_missing_title`, `test_parse_entry_returns_none_for_missing_url`, `test_parse_entry_returns_none_for_missing_description`, `test_parse_entry_returns_none_for_blank_title`, `test_parse_entry_returns_none_for_blank_url`, `test_parse_entry_returns_none_for_blank_description`, `test_ingest_all_logs_warning_for_dropped_entry` |
| 5 | Upsert uses `ON CONFLICT (url) DO NOTHING`; second run inserts zero duplicates | `test_scraper.py` | `test_ingest_all_uses_on_conflict_do_nothing` |
| 6 | Session commits immediately after each source is processed | `test_scraper.py` | `test_ingest_all_commits_after_each_source` |
| 7 | Failed source is skipped with one `WARNING`; remaining sources still run; all-sources failure raises `ServiceUnavailableError` | `test_scraper.py` | `test_ingest_all_skips_failed_source_continues_others`, `test_ingest_all_logs_warning_per_failed_source`, `test_ingest_all_raises_service_unavailable_when_all_sources_fail` |
| 8 | `ingest_all` returns `IngestResult(inserted: list[Article], fetched: int)` — `inserted` excludes conflict skips, `fetched` is pre-dedup count | `test_scraper.py` | `test_ingest_all_returns_inserted_articles_and_fetched_count`, `test_ingest_all_uses_on_conflict_do_nothing` |
| 9 | All three sources (`NYT`, `NPR`, `GUARDIAN`) are fetched on every `ingest_all` call | `test_scraper.py` | `test_ingest_all_fetches_all_three_sources` |
| 10 | With `SCRAPE_MAX_PER_SOURCE=3`, each source contributes at most 3 articles | `test_scraper.py` | `test_fetch_feed_caps_at_scrape_max_per_source` |
| 11 | No real network or DB calls in unit tests: `fetch_feed` mocks httpx + feedparser; `parse_entry` uses hand-crafted dicts; `ingest_all` mocks `fetch_feed` + `AsyncSession` | `test_scraper.py` | All `test_fetch_feed_*`, `test_parse_entry_*`, `test_ingest_all_*` (isolation visible from mock usage in each test) |
| 12 | `POST /api/scrape` happy path — 202 with `{"inserted": N, "fetched": M}` | `test_scrape.py` | `test_post_scrape_happy_path_returns_202_with_inserted_and_fetched` |
| 13 | `POST /api/scrape` all sources failed — 503 with `{"detail": "All RSS sources failed"}` | `test_scrape.py` | `test_post_scrape_all_sources_failed_returns_503` |
| 14 | `POST /api/scrape` idempotent — second call returns 202 with `inserted: 0` | `test_scrape.py` | `test_post_scrape_second_call_returns_202_with_zero_inserted` |

---

## Gap Analysis

**No gaps.** All 14 acceptance criteria have at least one mapped test.

Note on AC 1 — partial-failure resilience: the lifespan test (`test_lifespan_calls_ingest_all_after_migrations`) always mocks `ingest_all` to succeed; it does not exercise the lifespan with a partially-failing scraper. This is acceptable because AC 7's tests establish that `ingest_all` absorbs source failures without raising — so the lifespan has nothing special to handle. The combination fully covers the criterion.

---

## Pass / Fail Criteria

QA passes when:

1. Every acceptance criterion has at least one mapped test (zero UNCOVERED) — **met above**.
2. All mapped tests exit 0 with no failures and no skips.

**Command to run mapped tests:**

```bash
pytest -v backend/tests/unit/test_scraper.py backend/tests/routers/test_scrape.py
```

Run from the repo root (or adjust to your `pytest` invocation path). Both files must pass completely — no failures, no skips.
