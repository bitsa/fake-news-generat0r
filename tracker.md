# Tracker

| Task ID | Title | Iteration | Status | Spec | Dev | QA | Notes |
|---|---|---|---|---|---|---|---|
| schema | DB Schema & ORM | 1 | done | [schema-spec.md](docs/schema-spec.md) | [schema-dev.md](docs/schema-dev.md) | [schema-qa.md](docs/schema-qa.md) | Supersedes 1.1-dev.md. QA passed 46/46 (2026-05-06). |
| rss-scraper | RSS Scraper | 1 | done | [rss-scraper-spec.md](docs/rss-scraper-spec.md) | [rss-scraper-dev.md](docs/rss-scraper-dev.md) | [rss-scraper-qa.md](docs/rss-scraper-qa.md) | QA passed 21/21 (2026-05-07). |
| get-articles | GET /api/articles Feed Endpoint | 1 | done | [get-articles-spec.md](docs/get-articles-spec.md) | [dev](docs/get-articles-dev.md) | [qa](docs/get-articles-qa.md) | QA passed 16/16 (2026-05-07). |
| article-transformer | ARQ Transform Pipeline | 1 | done | [spec](docs/article-transformer-spec.md) | [dev](docs/article-transformer-dev.md) | [qa](docs/article-transformer-qa.md) | QA passed 48/48 (2026-05-07). |
| openai-transform | Real OpenAI call in transform worker (with dev mock kill-switch) | 1 | done | [spec](docs/openai-transform-spec.md) | [dev](docs/openai-transform-dev.md) | [qa](docs/openai-transform-qa.md) | QA passed 45/45 (2026-05-07). |
| chat-history | Chat — GET history endpoint (BE only) | 1 | done | [spec](docs/chat-history-spec.md) | [dev](docs/chat-history-dev.md) | [qa](docs/chat-history-qa.md) | QA passed 24/24 (2026-05-07). |
| chat-stream-skeleton | Chat — POST streaming endpoint (mock LLM, real SSE) | 1 | in_qa | [spec](docs/chat-stream-skeleton/chat-stream-skeleton-spec.md) | [dev](docs/chat-stream-skeleton/chat-stream-skeleton-dev.md) | [qa](docs/chat-stream-skeleton/chat-stream-skeleton-qa.md) | — |
| chat-llm | Chat — real OpenAI streaming (replaces mock generator + adds prompt builder) | 1 | in_dev | [spec](docs/chat-llm/chat-llm-spec.md) | [dev](docs/chat-llm/chat-llm-dev.md) | — | Depends on chat-stream-skeleton — see OQ-3. |
| sanitize | Sanitize scraped article text (HTML-decode, tag-strip, whitespace-collapse) | 2 | in_qa | [spec](docs/sanitize/sanitize-spec.md) | [dev](docs/sanitize/sanitize-dev.md) | — | — |
