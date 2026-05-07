# Tracker

| Task ID | Title | Iteration | Status | Spec | Dev | QA | Notes |
|---|---|---|---|---|---|---|---|
| schema | DB Schema & ORM | 1 | done | [schema-spec.md](docs/schema-spec.md) | [schema-dev.md](docs/schema-dev.md) | [schema-qa.md](docs/schema-qa.md) | Supersedes 1.1-dev.md. QA passed 46/46 (2026-05-06). |
| rss-scraper | RSS Scraper | 1 | done | [rss-scraper-spec.md](docs/rss-scraper-spec.md) | [rss-scraper-dev.md](docs/rss-scraper-dev.md) | [rss-scraper-qa.md](docs/rss-scraper-qa.md) | QA passed 21/21 (2026-05-07). |
| get-articles | GET /api/articles Feed Endpoint | 1 | done | [get-articles-spec.md](docs/get-articles-spec.md) | [dev](docs/get-articles-dev.md) | [qa](docs/get-articles-qa.md) | QA passed 16/16 (2026-05-07). |
| article-transformer | ARQ Transform Pipeline | 1 | done | [spec](docs/article-transformer-spec.md) | [dev](docs/article-transformer-dev.md) | [qa](docs/article-transformer-qa.md) | QA passed 48/48 (2026-05-07). |
| openai-transform | Real OpenAI call in transform worker (with dev mock kill-switch) | 1 | done | [spec](docs/openai-transform-spec.md) | [dev](docs/openai-transform-dev.md) | [qa](docs/openai-transform-qa.md) | QA passed 45/45 (2026-05-07). |
| chat-history | Chat — GET history endpoint (BE only) | 1 | done | [spec](docs/chat-history-spec.md) | [dev](docs/chat-history-dev.md) | [qa](docs/chat-history-qa.md) | QA passed 24/24 (2026-05-07). |
| chat-stream-skeleton | Chat — POST streaming endpoint (mock LLM, real SSE) | 1 | done | [spec](docs/chat-stream-skeleton/chat-stream-skeleton-spec.md) | [dev](docs/chat-stream-skeleton/chat-stream-skeleton-dev.md) | [qa](docs/chat-stream-skeleton/chat-stream-skeleton-qa.md) | QA passed 75/75 + 68/68 non-regression (2026-05-07). Sanitize-on-ingest drift on AC2/AC8 accepted; spec amendment to follow via /spec-update. |
| chat-llm | Chat — real OpenAI streaming (replaces mock generator + adds prompt builder) | 1 | done | [spec](docs/chat-llm/chat-llm-spec.md) | [dev](docs/chat-llm/chat-llm-dev.md) | [qa](docs/chat-llm/chat-llm-qa.md) | QA passed 50/50 + ruff/black clean (2026-05-07). AC25 soft gap accepted (option a) — convention-only coverage; see [chat-llm-01](docs/iteration-1/issues/chat-llm-01-ac25-no-suite-wide-network-egress-guard.md). Capture in decisions.md / future_work.md via /spec-update. |
| sanitize | Sanitize scraped article text (HTML-decode, tag-strip, whitespace-collapse) | 2 | done | [spec](docs/sanitize/sanitize-spec.md) | [dev](docs/sanitize/sanitize-dev.md) | [qa](docs/sanitize/sanitize-qa.md) | QA passed 35/35 (2026-05-07). |
