1) README is not yet a root doc.

Tech Debt :

1) The one thing I'd sanity-check
The plan says backend/worker "mounts code for dev" — that means a bind mount + uvicorn --reload. Worth confirming the worker has the equivalent (ARQ has --watch flags). Not a structure question, just a dev-loop ergonomics one for 0.C.

2) Your one-time host setup after this lands

brew install uv          # ✅ already done
make sync                # creates backend/.venv for IDE
make up                  # starts the stack
make health              # smoke check

1) adds requestId on ChatMessage + a unique constraint (articleId, requestId, role) — if an SSE stream drops and the client retries, no double-insert.
2) 429 handling + re-queue in ARQ worker

3) The transform_status addition I recommended isn't just about showing a spinner — it closes this durability gap. The flow would become:

POST /api/scrape
  → INSERT INTO articles ... ON CONFLICT (url) DO NOTHING
  → if inserted: INSERT INTO article_fakes (article_id, transform_status='pending')
  → enqueue ARQ job (best-effort — queue is an optimisation, not the source of truth)

ARQ worker
  → UPDATE article_fakes SET transform_status='processing'
  → call OpenAI
  → UPDATE article_fakes SET fake_title=..., transform_status='completed'
  → on failure: UPDATE article_fakes SET transform_status='failed', transform_error=...

Recovery (startup or cron)
  → SELECT article_id FROM article_fakes WHERE transform_status = 'pending' AND created_at < NOW() - interval '5 min'
  → re-enqueue any stuck ones
The DB becomes the source of truth. The ARQ queue becomes a fast-path delivery mechanism, not the only record that work exists.

1) IMPROTANT :
After POST /api/scrape returns, the frontend is responsible for showing results without requiring a manual refresh. Use React Query polling with a smart stop condition.

Flow:

POST /api/scrape returns synchronously with {enqueued, skipped, sources_scraped} — no change to the endpoint
On success, React Query immediately invalidates the articles query → articles appear in the feed with transform_status: 'pending' shown as "Processing..."
React Query starts polling GET /api/articles every 3 seconds
Polling stops automatically when no article has transform_status of pending or processing — all have reached a terminal state (completed or failed)
Stop condition (TypeScript):

refetchInterval: (data) =>
  data?.some(a => a.transform_status === 'pending' || a.transform_status === 'processing')
    ? 3000
    : false

    This above code should have a logic to only keep polling for x long or x times. 
    
Dependency: This requires transform_status as a column on article_fakes (values: pending, processing, completed, failed). Without it the frontend cannot distinguish "still transforming" from "permanently failed" and has no clean stop condition.

What this avoids: No WebSocket, no SSE on the scrape endpoint, no new scrape_jobs table, no new status endpoints. React Query's refetchInterval handles the entire polling lifecycle natively.

1)

Tech DebT !!! Important
 Prompt for fresh agent
The RSS scraper ingestion path (PR #2) is too quiet. We just spent an hour debugging a silent NotNullViolationError that never appeared in docker compose logs backend even though log.warning(..., exc_info=True) was in place. Two things to fix:

1. Fix log buffering. Add ENV PYTHONUNBUFFERED=1 to backend/Dockerfile. Without this, Python buffers stdout in non-TTY environments and any logs in flight when the container restarts are lost. This is almost certainly why we couldn't see the scraper errors.

2. Add lightweight INFO-level logs to make the ingestion flow visible. Don't over-instrument — just enough that someone tailing logs can follow the shape of a scrape. Specifically:

In app/main.py lifespan: log startup.migrations.begin and startup.migrations.complete around _run_migrations(). Log startup.scrape.begin before the scrape (the existing startup.scrape.complete stays).
In app/services/scraper.py:
fetch_feed: log scraper.fetch.begin source=<X> before the GET and scraper.fetch.ok source=<X> entries=<N> elapsed_ms=<M> after parse.
ingest_all: at the top, log scraper.ingest.begin sources=<N>. After each source's commit, log scraper.source.ok source=<X> fetched=<N> inserted=<M>. At the end log scraper.ingest.complete fetched=<total> inserted=<total> failed=<N>.
Keep the existing scraper.entry.dropped and scraper.source.failed warnings — those are correct.
Constraints:

INFO level for happy-path events, WARNING for drops/failures (already in place).
Use the existing log = logging.getLogger(__name__) pattern. Don't introduce a logging library or change logging_config.py beyond what's needed.
Keep keys/values machine-greppable: key=value style, no f-string sentences.
No new dependencies. No metric/tracing libraries.
Verify by:

docker compose down -v && docker compose up -d
docker compose logs backend -f — you should see migrations begin/end, scrape begin, three scraper.fetch.ok lines (NYT/NPR/Guardian), three scraper.source.ok lines, then scraper.ingest.complete and startup.scrape.complete.
To prove buffering is fixed, temporarily break a feed URL in app/sources.py, restart, and confirm the scraper.source.failed warning with traceback appears in docker compose logs backend — not just on manual repro.
