# Architecture

> **AGENTS: Read this before writing any code.** This document describes the system's components, how they connect, and how data flows through them. If you add a component or change a connection, update this document.
>
> **Who reads this:** Dev agents (to understand integration points) and Spec agents (to scope tasks correctly). QA agents use this for context but test against `contracts.md`, not this doc.
>
> **Doc workflow:** Per-task plans live in `docs/iteration-{N}/`:
> `{task-id}-spec.md` is written first, then `{task-id}-dev.md`, then `{task-id}-qa.md` (QA never reads dev).

---

## Component Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                         Host Machine                            │
│                                                                 │
│  Browser                                                        │
│  └─── localhost:5173                                            │
│            │                                                    │
│            ▼                                                    │
│  ┌─────────────────┐     docker network: fakenews_net          │
│  │   frontend      │◄──────────────────────────────────────────┤
│  │  Vite + React   │                                           │
│  │  :5173          │                                           │
│  │                 │  /api/* proxy                             │
│  │  React Query    ├─────────────────────►┌──────────────────┐ │
│  │  fetch-event-   │                      │    backend       │ │
│  │  source (SSE)   │◄─────────────────────┤  FastAPI + uvi.  │ │
│  └─────────────────┘    SSE stream        │  :8000           │ │
│                                           │                  │ │
│                                           │  Pydantic Sett.  │ │
│                                           │  stdlib logging  │ │
│                                           └────┬──────┬──────┘ │
│                                                │      │        │
│                                     SQLAlchemy │      │ redis  │
│                                     asyncpg    │      │ client │
│                                                ▼      ▼        │
│                                    ┌────────┐ ┌──────────────┐ │
│                                    │postgres│ │    redis     │ │
│                                    │pgvector│ │  :6379       │ │
│                                    │:5432   │ │              │ │
│                                    │        │ │ ARQ queue    │ │
│                                    │ tables:│ │  (broker     │ │
│                                    │ articles│ │   only)      │ │
│                                    │ article │ └──────┬───────┘ │
│                                    │ _fakes  │        │         │
│                                    │ chat_msg│        │         │
│                                    │         │       │         │
│                                    │         │       │ ARQ     │
│                                    │         │       │ jobs    │
│                                    └────────┘       ▼          │
│                                              ┌──────────────┐  │
│                                              │    worker    │  │
│                                              │  ARQ worker  │  │
│                                              │  (same image │  │
│                                              │   as backend)│  │
│                                              │              │  │
│                                              │  Transform   │  │
│                                              │  jobs        │  │
│                                              └──────┬───────┘  │
│                                                     │          │
│                                              OpenAI API        │
│                                              (external)        │
│                                                     │          │
│                                              ┌──────▼───────┐  │
│                                              │   OpenAI     │  │
│                                              │  (gpt-4o-mini│  │
│                                              │   chat/xform)│  │
│                                              └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Services (Docker Compose)

| Service | Image | Port | Role |
|---|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | 5432 (internal) | Primary datastore |
| `redis` | `redis:7-alpine` | 6379 (internal) | ARQ job queue (broker only — see ADR-9) |
| `backend` | `./backend/Dockerfile` | 8000 | FastAPI API server |
| `worker` | `./backend/Dockerfile` | — | ARQ worker (same image, different command) |
| `frontend` | `./frontend/Dockerfile` | 5173 | Vite dev server |

**Startup order (health-gated):**

- `postgres` and `redis` start first with real healthchecks (`pg_isready`, `redis-cli ping`)
- `backend` and `worker` `depends_on` both with `condition: service_healthy`
- `frontend` starts independently (it calls backend via Vite proxy at request time, not startup)

**Internal networking:** All services share `fakenews_net` bridge network. Services call each other by service name (e.g., `http://backend:8000`, `redis://redis:6379`).

---

## Data Flow Walkthroughs

### 1. Scrape Pipeline (Manual Trigger)

```text
User clicks "Scrape Now"
    │
    ▼
Frontend: POST /api/scrape
    │
    ▼
backend: ScrapeOrchestrator
    ├── Acquire single-flight lock (asyncio); if already held, return 409
    ├── For each source in app.sources.FEED_URLS (keyed by `Source` StrEnum):
    │       ├── HTTP GET feed_url (feedparser)
    │       ├── Parse entries → [{title, description, url, published_at}]
    │       ├── Take at most SCRAPE_MAX_PER_SOURCE entries (feed order)
    │       ├── Compute content_hash = SHA256(title + description)
    │       ├── INSERT ... ON CONFLICT (content_hash) DO NOTHING
    │       └── If row inserted: enqueue ARQ transformation job
    │
    └── Return {enqueued, skipped_duplicates, sources_scraped}
    │
    ▼
redis: ARQ queue (job: transform_article, payload: article_id)
    │
    ▼
worker: ARQ task runs
    ├── Load article from DB
    ├── Render prompt template
    ├── Call OpenAI completions API
    ├── Parse response → {fake_title, fake_description}
    ├── INSERT INTO article_fakes
    │       (article_id, fake_title, fake_description, model, temperature)
    │   VALUES (...)
    │   ON CONFLICT (article_id) DO UPDATE SET ...   (re-runs replace prior fake)
    └── Log: one start line + one end line per job (article_id, model)
```

**Single-flight guard:** `POST /api/scrape` acquires a process-local asyncio lock; concurrent calls return 409 immediately. Multi-instance deployments would need a Redis-backed lock — deferred to `future_work.md`.

**Retry behavior:** ARQ runs each job once (`max_tries=1`, ADR-2). On failure: log and skip — no `article_fakes` row is inserted (ADR-15). The article remains in "Processing…" indefinitely and requires a manual re-run to recover; a future scrape will not re-enqueue it because `content_hash` already exists.

---

### 2. Read Article Feed

```text
Frontend mount: useQuery(["articles"])
    │
    ▼
GET /api/articles
    │
    ▼
backend: ArticleService.list_articles()
    ├── SELECT articles.*, article_fakes.fake_title, article_fakes.fake_description,
    │          article_fakes.model, article_fakes.temperature,
    │          article_fakes.created_at AS fake_created_at
    │     FROM articles LEFT JOIN article_fakes ON article_fakes.article_id = articles.id
    ├── `articles.source` is a Postgres enum (source_type) — returned as a string in JSON; no JOIN for source, no lookup (see ADR-16)
    └── Return flat objects: fake-side fields are null when no article_fakes row exists (no pagination, no server-side filter — deferred to future_work)
    │
    ▼
React Query caches response (staleTime: 30s)
    │
    ▼
Frontend renders ArticleCard for each item
    ├── Filters by source client-side (no extra fetch)
    └── Shows fake_title + fake_description if non-null
        Shows "Processing..." if fake_title is null
```

---

### 3. Chat with Streaming

```text
User types message → clicks Send
    │
    ▼
Frontend: POST /api/articles/{id}/chat  body: {message}
    using @microsoft/fetch-event-source
    │
    ▼
backend: ChatService.chat_stream(article_id, user_message)
    ├── Validate article exists (404 if not)
    ├── INSERT chat_messages (role=user, content=user_message)
    ├── Load article (original + fake_* columns from same row)
    ├── Load chat history (all prior messages)
    ├── Build OpenAI messages array:
    │       [system prompt] + [history] + [user message]
    ├── Open StreamingResponse (SSE)
    └── Stream loop:
            ├── For each token from OpenAI:
            │       yield f"data: {json.dumps({'token': token})}\n\n"
            ├── On completion:
            │       INSERT chat_messages (role=assistant, content=full_text)
            │       yield "data: [DONE]\n\n"
            └── On OpenAI error:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    (partial content NOT saved)
    │
    ▼
Frontend: @microsoft/fetch-event-source onmessage callback
    ├── Parses each event
    ├── If {token}: append to streaming bubble in real time
    ├── If [DONE]: finalize bubble, refetch message history
    └── If {error}: show error state, unlock input
```

---

## Backend Internal Structure

```text
backend/
├── app/
│   ├── main.py              # FastAPI app factory, middleware, exception handlers
│   ├── config.py            # Pydantic Settings, reads all env vars
│   ├── db.py                # Async engine, session factory (AsyncSessionLocal)
│   ├── redis_client.py      # Redis connection helper (named *_client to avoid shadowing the `redis` PyPI package)
│   ├── sources.py           # `Source` StrEnum (single source of truth) + `FEED_URLS` — see ADR-16
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── article.py       # original-side schema only (ADR-5)
│   │   ├── article_fake.py  # 1:1 with articles, fake-side schema (ADR-5)
│   │   └── chat_message.py
│   ├── schemas/             # Pydantic request/response schemas
│   ├── routers/             # FastAPI routers, one per domain
│   │   ├── health.py
│   │   ├── scrape.py
│   │   ├── articles.py
│   │   └── chat.py
│   ├── services/            # Business logic, called by routers
│   │   ├── scrape.py
│   │   ├── articles.py
│   │   └── chat.py
│   ├── worker/              # ARQ tasks
│   │   ├── settings.py      # ARQ WorkerSettings
│   │   └── tasks.py         # transform_article task
│   └── scraper/             # RSS fetching + parsing (pure functions)
│       └── rss.py
├── migrations/
│   ├── env.py               # Async-configured Alembic env
│   └── versions/            # Hand-written migration files
├── tests/
├── alembic.ini
└── pyproject.toml
```

---

## Frontend Internal Structure

```text
frontend/
├── src/
│   ├── main.tsx             # React root, QueryClientProvider — mounts <FeedPage /> directly in 0.C; routing (react-router-dom) arrives in 1.8
│   ├── pages/
│   │   ├── FeedPage.tsx     # Route "/"
│   │   └── ArticlePage.tsx  # Route "/articles/:id"
│   ├── components/
│   │   ├── ArticleCard.tsx
│   │   ├── ChatPanel.tsx
│   │   └── HealthStatus.tsx
│   ├── hooks/
│   │   ├── useArticles.ts   # React Query hook for article list
│   │   ├── useArticle.ts    # React Query hook for single article
│   │   └── useChat.ts       # SSE stream management
│   ├── types/               # TypeScript types from contracts.md
│   │   └── api.ts
│   └── api/                 # Fetch wrappers
│       └── client.ts
├── vite.config.ts           # Proxy: /api/* → http://backend:8000
├── tsconfig.json            # strict: true
└── package.json
```

---

## External Dependencies

| Dependency | Purpose | Notes |
|---|---|---|
| OpenAI API | Text transformations + chat + embeddings (Iter 3) | Mocked in all tests |
| RSS feeds (NYT, NPR, Guardian) | Source articles | Network calls mocked in unit tests; integration tests may use real feeds |

No other external dependencies. Auth, storage, CDN, etc. are out of scope.
