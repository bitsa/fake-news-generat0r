# Sanitize Scraped Article Text — Spec

## Source

**File:** `/Users/bitsa/.claude/plans/let-s-plan-what-and-modular-river.md` (task draft authored
by the user). Verbatim scope:

> Add a single tiny function `clean_text(s) -> str` and call it from `parse_entry` for both
> `title` and `description`. Use Python stdlib only — no `bleach`, no BeautifulSoup. … `html.unescape`
> first … strip HTML tags via `re.sub(r"<[^>]+>", " ", s)` … collapse whitespace via
> `re.sub(r"\s+", " ", s).strip()`.

This spec covers cleaning of the `title` and `description` fields produced by
`scraper.parse_entry` ([backend/app/services/scraper.py:47-66](../../backend/app/services/scraper.py#L47-L66))
before they are persisted to the `articles` table. It does **not** cover cleaning of LLM-generated
content in `article_fakes`, URL validation, or any change to the `articles` schema.

---

## Goal

Ensure that the `title` and `description` fields stored in the `articles` table for every scraped
entry are plain, prose-readable text — free of HTML tags, free of HTML entities, and with
collapsed whitespace. Today, RSS summaries from NYT / NPR / Guardian routinely contain `<p>`,
`<a>`, `<img>`, `<br/>`, `&amp;`, `&#39;`, `&nbsp;`, etc., which (a) burn LLM tokens and confuse
the transform prompt and (b) render as literal markup or garbage in the frontend. A single
stdlib-only cleaning step in the scrape path closes both at once with no new dependencies.

---

## User-Facing Behavior

- `docker-compose up` (or a fresh `POST /api/scrape`) populates the `articles` table with rows
  whose `title` and `description` fields contain no `<...>` substrings and no HTML entities such
  as `&amp;`, `&lt;`, `&#39;`, `&nbsp;`.
- An RSS entry whose summary is only HTML/whitespace (e.g. `<p></p>` or `&nbsp; \n`) is dropped
  by the scraper with one `WARNING` log line — the same dropped-entry behavior already exposed
  for entries missing a field.
- `POST /api/scrape` returns the same `202 Accepted` envelope as before; the only externally
  observable change is the cleanliness of the persisted text.
- Article URLs (`articles.url`) are unchanged in shape — query strings, fragments, and percent
  encodings survive end-to-end. URLs are not passed through HTML cleaning.
- `GET /api/articles` returns `title` and `description` fields free of HTML markup and entities.
- The transform worker prompt sent to OpenAI for any newly scraped article contains no HTML tags
  or entities in its title/description payload.

---

## Acceptance Criteria

A QA agent can verify each item below without reading any implementation file.

1. **No tags in stored title/description** — after a successful scrape run, no row in the
   `articles` table written by that run has a `title` or `description` value containing the
   substring `<` followed by any character followed by `>` (i.e. matches the regex `<[^>]+>`).

2. **No HTML entities in stored title/description** — after a successful scrape run, no row in
   the `articles` table written by that run has a `title` or `description` value containing
   any of the literal substrings `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#39;`, `&nbsp;`, or any
   numeric character reference of the form `&#NNN;` / `&#xNN;`.

3. **Entities decoded, not stripped** — given an RSS entry whose title is
   `Apples &amp; oranges &#8217;s tale`, the persisted `articles.title` reads
   `Apples & oranges ’s tale` (the entities are converted to their character equivalents, not
   removed).

4. **Tag stripping does not fuse adjacent words** — given an RSS summary
   `<p>Hello</p><p>world</p>`, the persisted `articles.description` contains both `Hello` and
   `world` separated by at least one whitespace character (i.e. the strings are not fused into
   `Helloworld`).

5. **Whitespace collapsing** — runs of whitespace in the input (spaces, tabs, newlines, mixes
   of these) appear in the persisted value as single spaces, with no leading or trailing
   whitespace.

6. **Empty-after-clean drop** — an RSS entry whose summary is a string containing only HTML
   tags and/or whitespace (examples: `<p></p>`, `<br/><br/>`, `&nbsp; \n`, `   `) causes
   `parse_entry` to return `None`, the entry is not inserted, and exactly one
   `scraper.entry.dropped` `WARNING` is emitted (matching the existing dropped-entry log
   contract from the `rss-scraper` task).

7. **Empty title-after-clean drop** — symmetrically, an RSS entry whose title is only HTML
   tags and/or whitespace causes the entry to be dropped with the same single `WARNING` line.

8. **Idempotent** — applying the cleaning logic to an already-clean string produces the same
   string. In particular, a value that was just persisted by the scraper, if fed back into the
   same cleaner, is unchanged. (Verifiable via the `clean_text` unit tests.)

9. **URL untouched by cleaning** — given an RSS entry with `link =
   "https://example.com/path?a=1&b=2#frag"`, the persisted `articles.url` is exactly
   `https://example.com/path?a=1&b=2#frag` (no entity decoding, no `&amp;` collisions, no
   query/fragment loss). URL handling continues to use a plain `.strip()`.

10. **Stdlib only** — the new sanitization module imports only from the Python standard library
    (e.g. `html`, `re`). No new third-party dependency is added to `pyproject.toml` /
    `uv.lock`.

11. **Unit tests for the cleaner** — `backend/tests/unit/test_sanitize.py` exists and covers,
    at minimum: entity decoding (`&amp;`, `&#39;`, `&nbsp;`), tag stripping for `<p>`,
    `<a href="...">`, `<img/>`, `<br/>`, whitespace collapsing across newlines/tabs, the empty
    result case, and idempotence. All tests pass under
    `cd backend && uv run pytest tests/unit/test_sanitize.py -v`.

12. **Unit tests for parse_entry HTML handling** — `backend/tests/unit/test_scraper.py` is
    extended with at least: (a) one case where the input feedparser entry has HTML in title
    and summary and the resulting `Article` carries cleaned text, and (b) one case where the
    summary is `"<p></p>"` and `parse_entry` returns `None`. Tests pass under
    `cd backend && uv run pytest tests/unit/test_scraper.py -v`.

13. **No regression to existing scraper acceptance criteria** — every acceptance criterion in
    [docs/rss-scraper/rss-scraper-spec.md](../rss-scraper/rss-scraper-spec.md) (entry cap,
    upsert, per-source commit, per-source error isolation, source coverage, idempotent
    `POST /api/scrape`, etc.) continues to hold. In particular, AC 4 (drop with single
    `WARNING` on missing field) still fires for entries that become blank only after cleaning
    (covered above in AC 6 / AC 7).

14. **Backend lint and format pass** — `ruff` and `black` pass on the new and modified files
    with no new ignores or `# noqa` markers introduced by this task.

---

## Out of Scope

- Switching to `bleach`, `BeautifulSoup`, or any other HTML parser. Stdlib regex is explicitly
  chosen for simplicity; robustness against pathological HTML is deferred and listed as future
  work.
- Cleaning `article_fakes.title` / `article_fakes.description`. Those are produced by our own
  LLM call against already-cleaned input — they are not feed-derived and are out of scope here.
- URL validation, scheme allowlisting, or any URL transformation beyond the existing `.strip()`.
- Detecting or rejecting prompt-injection patterns in feed text.
- Any change to the `articles` table schema or its migrations.
- Re-cleaning historical rows already in the database. The cleaning applies to entries scraped
  after this task ships; backfill of pre-existing rows is not required.
- Changes to the transform worker prompt construction. The worker continues to read whatever is
  in `articles.title` / `articles.description` verbatim.
- Editing `docs/rss-scraper/rss-scraper-spec.md` to record this new behavior. The plan suggests
  adding a bullet to that doc; whether to do so is flagged below as an open question.

---

## Decisions

The following points were raised as open questions during spec review and resolved by the user
on 2026-05-07. They are recorded here as decisions, not open questions.

1. **The existing `rss-scraper` spec is left unchanged.**
   [docs/rss-scraper/rss-scraper-spec.md](../rss-scraper/rss-scraper-spec.md) is historical and
   not amended by this task. This spec stands alone; AC 13 cross-references the prior spec only
   to assert non-regression.

2. **`html.unescape` covers all character references.** AC 2 forbids named, decimal, and
   hexadecimal HTML character references from appearing in the persisted text.
   `html.unescape` from the Python stdlib handles all three forms. No additional handling is
   added.

3. **`<script>` / `<style>` text content survives as plain text.** The chosen approach replaces
   any tag with a single space — it does not specifically remove the tag's *contents*. A stray
   `<script>alert(1)</script>` in a feed summary would persist as the literal text `alert(1)`.
   This is accepted for MVP given the trusted three-source list; harder sanitization is future
   work (see "Out of Scope").

4. **No length cap or Unicode normalization.** The spec imposes neither a maximum title length
   nor any NFC/NFKC normalization. Existing column constraints in `articles` continue to govern
   length; no normalization is performed by `clean_text`.

5. **Empty-after-clean reuses the existing dropped-entry log.** AC 6 / AC 7 reuse the existing
   `scraper.entry.dropped` `WARNING` key from the `rss-scraper` task verbatim. No new log key
   is introduced.
