1) Next thing in the morning : Messaging with the AI !!!

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
2) 429 handling + re-queue in ARQ worker < --- this was dereferred for the scope. BUt let's use this to put together a document at the end - what I'd add given more time. Retry for this + re-queue or exponential backoff with failed proper handling

3) IMPROTANT :
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

1.

Task: Add a periodic recovery sweep for stuck article_fakes rows. Do this when creating a cron job for scraping

Context: Today, recover_stale_pending (in backend/app/services/transformer.py) only runs once, in the FastAPI lifespan startup hook. If the API process stays up for days/weeks while individual ARQ workers crash, orphan rows with transform_status='pending' and created_at older than transform_recovery_threshold_minutes (default 5) will accumulate in the DB and never get re-enqueued until the next restart.

What to do: Register recover_stale_pending as an ARQ cron job in WorkerSettings.cron_jobs (in backend/app/workers/transform.py) so it runs every N minutes on the worker side — turning recovery from a startup-only safety net into a continuous background sweep. Suggested cadence: every 2–5 minutes. The worker function will need to build its own AsyncSession and reuse the existing ArqRedis from ctx, the same way transform_article does. Keep the lifespan call too — belt and suspenders is fine.

Constraints:

Do not add failed/processing/transform_error to the schema — two-state lifecycle (pending → completed or row deleted) is intentional. See feedback_schema_no_failure_states.md.
No new infra (no Celery beat, no external scheduler) — must use ARQ's built-in cron_jobs.
Add a unit test that verifies the cron entry is registered and points at recover_stale_pending.

1. Good to have : when giving article to AI : ask them to give back a 1 word category name out of possible outputs : "Climate" "tech" "markets" "politics" etc etc.

2. Good to have : Judge model for generated fake articles

3. when parsing RSS - do we want validation ?

4. in the FE : export type SourceId = "NYT" | "NPR" | "Guardian";
should we collect it from the articles request instead ?
let's think a bit


5. Cron Job - MUST DO easy win
6. Zustand Store - because the assignment mentions it