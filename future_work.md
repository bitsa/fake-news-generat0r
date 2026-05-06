# Future Work — "What I'd Do With More Time"

This is the explicit list of things consciously deferred. Use directly in the Loom recording and interview discussion.

---

## Observability & Production Readiness

- **Sentry** for error tracking — capture frontend + backend exceptions with breadcrumbs and user context
- **OpenTelemetry traces** end-to-end — especially valuable for tracing a single user action across HTTP → ARQ → OpenAI calls. LLM-heavy apps benefit massively from spans showing prompt assembly, OpenAI latency, post-processing
- **Prometheus + Grafana** for metrics — queue depth, transformation latency, tokens-per-second, cache hit rate, OpenAI error rate
- **LangSmith / Langfuse / Helicone** — LLM-specific observability: trace prompts, see token usage trends, evaluate prompt versions, replay failed runs. **This is the one I'd add first** — it's purpose-built for LLM apps and would have made debugging much easier
- **Cost tracking + budget alerts** on OpenAI usage with hard limits
- **Split `/health` into `/health/live` + `/health/ready`** — the current single endpoint conflates "process alive" with "dependencies reachable". Once the app runs somewhere with separate liveness/readiness probes (Kubernetes), splitting lets the orchestrator restart on liveness failure but only drain traffic on readiness failure

---

## LLM Engineering

- **Semantic chat cache** — embed user query + article context, look up similar prior queries with cosine similarity threshold, return cached answer if hit. Same idea Helicone/Portkey productize. Saves cost + latency on repeated questions like "summarize this article"
- **Prompt evals** — test set of articles with golden satirical outputs, run on prompt changes, compare via LLM-as-judge or human review
- **Streaming structured output** for chat — e.g., "extract entities" returns JSON streamed progressively (using tool calls + streaming)
- **Multi-model A/B** — same article transformed with different models, store side-by-side, compare quality
- **Prompt injection defense** — current chat just feeds user input straight to LLM. With multi-tenant or sensitive data, would need input sanitization and output filtering

---

## Scaling

- **Horizontal API replicas** — would require Redis pub/sub for SSE coordination, sticky sessions or stateless reconnection
- **Read replicas** for the article feed once it grows
- **Dead-letter queue** for permanently failed transformations + a dashboard to inspect them
- **Smarter retry strategies** — exponential backoff with jitter, circuit breaker on OpenAI outages
- **Batch the embedding API calls** — currently one per article; OpenAI supports batched embeddings, much cheaper at scale

---

## Product

- **Authentication + multi-user chat history** — currently chat is shared per-article across all users (see ADR-11 in `decisions.md` for migration path)
- **Bookmark / favorite articles**
- **Search** — full-text on titles + descriptions, semantic via existing embeddings
- **Edit prompt per article** — let user choose tone (sarcastic, absurdist, dry) and re-transform on demand
- **Compare versions side-by-side** UI when multiple prompt versions exist for one article

---

## Frontend Quality

- **Optimistic UI** for chat — render user message + skeleton response immediately
- **Virtualized list** for the feed once it grows past ~100 items
- **Accessibility pass** — keyboard nav, ARIA labels, contrast audit, screen reader testing
- **Mobile responsive design** beyond "doesn't break"
- **Skeleton loading states** instead of spinners
- **i18n scaffolding** if going international

---

## Testing

- **E2E tests with Playwright** — full user flows in a real browser
- **Visual regression tests** for critical UI states
- **Load testing** the scrape + transform pipeline under volume
- **Chaos testing** — randomly kill OpenAI mock during streams, verify graceful degradation

---

## DevOps / CI

- **Pre-commit hooks** (lint, format, typecheck) via `husky` + `lefthook`
- **Dependabot** or Renovate for security updates
- **Container image scanning** in CI
- **Infrastructure as code** — Terraform for whatever cloud you'd deploy to
- **Separate staging environment** with anonymized real data

---

## API

- **Pagination on `GET /api/articles`** — `limit` / `offset` query params with a `total` count in the response. Deferred from Iter 1 since the MVP feed is small enough to return in full; revisit once article volume grows or the frontend adds a virtualized list.

---

## Data / Schema

- **Article tags** — extract topics during transformation, enable topic-based filtering
- **Source health monitoring** — track per-source success rate, alert if one feed dies
- **Soft deletes** for articles + GDPR-style data retention policy

---

## Loom Talking Track (Compressed)

> "With more time, in priority order:
>
> 1. **LLM observability** — Langfuse or LangSmith. The single biggest gap right now is I can't easily trace why a specific transformation went weird or compare prompt versions empirically.
> 2. **Semantic chat cache** — embed queries, return cached answers on similarity hit. Big cost win.
> 3. **Prompt evals** — golden test set + automated comparison on prompt changes.
> 4. **Sentry + OpenTelemetry** for production-grade error tracking and tracing.
> 5. **Auth + per-user chat history** — current model is per-article, fine for demo but not real product.
> 6. **Pre-commit hooks + Dependabot** — should have been there from day one in a real project."
