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
