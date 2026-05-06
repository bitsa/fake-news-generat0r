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
Dependency: This requires transform_status as a column on article_fakes (values: pending, processing, completed, failed). Without it the frontend cannot distinguish "still transforming" from "permanently failed" and has no clean stop condition.

What this avoids: No WebSocket, no SSE on the scrape endpoint, no new scrape_jobs table, no new status endpoints. React Query's refetchInterval handles the entire polling lifecycle natively.

1) next steps : AI transformation + queue
Will need to break this up into 2 tasks openAI integration and queue set up and flow.

Task draft: article-transformer (next task after rss-scraper is done)

Context:
  rss-scraper is complete. scraper.ingest_all(session) runs on startup,
  upserts articles, and returns list[Article] for newly inserted rows.
  No article_fakes rows exist yet. The ARQ worker infrastructure exists
  (arq is installed, redis is running via Docker Compose) but is unused.

What this task adds:

  1. Immediately after scraper.ingest_all() returns, for each new Article:
       INSERT INTO article_fakes (article_id, transform_status='pending')
       Enqueue an ARQ job: transform_article(article_id)
     Both writes happen before the lifespan continues. Pending rows are
     the durability record — if the queue is wiped, the row survives.

  2. An ARQ worker job (backend/app/worker.py):
       async def transform_article(ctx, article_id: int)
       - Fetch the Article from DB
       - Call OpenAI (mock in tests) to generate fake_title + fake_description
         using settings.openai_model_transform / openai_temperature_transform
       - On success: UPDATE article_fakes SET transform_status='completed',
         title=..., description=..., model=..., temperature=...
       - On failure: DELETE FROM article_fakes WHERE article_id=...
         Log the error. No retry (max_tries=1).

  3. A new coordinator: backend/app/services/ingestor.py
       async def run(session: AsyncSession, arq_pool: ArqRedis) -> int
       - Calls scraper.ingest_all(session) → list[Article]
       - Inserts pending article_fakes rows for each
       - Enqueues ARQ jobs (best-effort — log warning if enqueue fails,
         do not abort)
       - Returns count of jobs enqueued
     main.py lifespan switches from scraper.ingest_all() to ingestor.run().
     scraper.py is untouched.

  4. Recovery: on startup, re-enqueue any article_fakes rows where
     transform_status='pending' AND created_at < NOW() - interval '5 min'
     (handles crash-during-flight from a prior run).

Files to create:
  backend/app/services/ingestor.py
  backend/app/worker.py
  backend/tests/unit/test_ingestor.py
  backend/tests/unit/test_worker.py

Files to modify:
  backend/app/main.py — switch lifespan call; wire ARQ pool

Out of scope:
  API endpoints, frontend, scheduled scraping, retry storms, DLQ.
  scraper.py is not modified.

1) expose the endpoint for article quering.
