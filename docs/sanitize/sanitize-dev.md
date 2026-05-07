# Sanitize Scraped Article Text — Dev Plan

## MUST READ FIRST

- [docs/sanitize/sanitize-spec.md](sanitize-spec.md) — source of truth for behavior
- [context.md](../../context.md) — Python standards (async-only, type hints,
  `X | None`, `ruff`/`black`, no `os.environ`), logging rules
- [plans/plan.md](../../plans/plan.md) — workflow / spec-driven philosophy
- Source files examined:
  - [backend/app/services/scraper.py](../../backend/app/services/scraper.py)
    — `parse_entry` (lines 47-66) and `ingest_all` (the only callers of `parse_entry`,
    and the site of the existing `scraper.entry.dropped` `WARNING`)
  - [backend/app/sources.py](../../backend/app/sources.py) — `Source` StrEnum
  - [backend/app/models.py](../../backend/app/models.py) — `Article` ORM model
    (no schema change needed; AC 6 / spec "Out of Scope")
  - [backend/tests/unit/test_scraper.py](../../backend/tests/unit/test_scraper.py)
    — existing test patterns we will extend (notably the `_entry()` helper
    and the `caplog`-based dropped-entry assertion)
  - [backend/pyproject.toml](../../backend/pyproject.toml) — to confirm no
    new dependency is added (AC 10)

---

## Files to touch / create

Create:

- `backend/app/services/sanitize.py` — new module exposing `clean_text`.
- `backend/tests/unit/test_sanitize.py` — unit tests for `clean_text` (AC 11).

Modify:

- `backend/app/services/scraper.py` — call `clean_text` on `title` and
  `summary` inside `parse_entry`. Leave `link` / URL handling on its own
  `.strip()` path (AC 9). No other changes.
- `backend/tests/unit/test_scraper.py` — extend with HTML-handling cases
  for `parse_entry` (AC 12).

Not touched:

- `backend/pyproject.toml`, `backend/uv.lock` — stdlib only (AC 10).
- Any Alembic migration, `Article` model, or DB schema.
- `backend/app/services/openai_transform.py` — transform worker reads
  cleaned values verbatim from `articles`, no change needed (spec "Out of
  Scope" #6).
- `docs/rss-scraper/rss-scraper-spec.md` — left unchanged per spec
  Decision #1.

---

## Interfaces / contracts to expose

### New module — `backend/app/services/sanitize.py`

```python
def clean_text(s: str) -> str: ...
```

Behavior contract (derived from spec AC 1-8):

- Input: any `str` (callers pass values already coerced from feedparser via
  `(entry.get(...) or "")`). The function does not accept `None`.
- Order of operations:
  1. `html.unescape(s)` — converts named, decimal, and hex character
     references to their character equivalents (AC 2, AC 3, Decision #2).
  2. `re.sub(r"<[^>]+>", " ", ...)` — replaces every HTML tag with a single
     space, ensuring adjacent words separated only by tags do not fuse
     (AC 4).
  3. `re.sub(r"\s+", " ", ...).strip()` — collapses whitespace runs and
     trims leading/trailing whitespace (AC 5).
- Returns the cleaned string. May be empty (`""`) if the input contained
  only tags / entities / whitespace; callers are responsible for treating
  empty as "drop" (AC 6 / AC 7).
- Idempotent: `clean_text(clean_text(x)) == clean_text(x)` (AC 8).
- Stdlib only — imports `html` and `re`. No third-party imports (AC 10).

The two regexes are module-level constants (compiled with `re.compile`)
so they are not recompiled per call. Names: `_TAG_RE`, `_WS_RE` (private,
underscore-prefixed per `context.md` Python naming standards).

### Modified contract — `parse_entry`

The signature is unchanged:

```python
def parse_entry(entry: RawEntry, source: Source) -> Article | None: ...
```

Internally, `title` and `description` are passed through `clean_text` after
the existing `(entry.get(...) or "").strip()` extraction. The blank-check
(`if not title or not url or not description: return None`) operates on
the **cleaned** values — this is what makes AC 6 / AC 7 ("empty after
clean drops the entry") work without any change to `ingest_all` or the
`scraper.entry.dropped` log line, which already fires once per dropped
entry inside `ingest_all`.

`url` is **not** passed through `clean_text` (AC 9). It continues to use
`(entry.get("link") or "").strip()`.

### No change to other contracts

- `IngestResult`, `fetch_feed`, `ingest_all`: unchanged.
- `POST /api/scrape` envelope: unchanged (spec User-Facing Behavior).
- `articles` table schema and migrations: unchanged.

---

## Implementation plan

1. **Create `backend/app/services/sanitize.py`.**
   - Imports: `import html`, `import re`.
   - Module-level: `_TAG_RE = re.compile(r"<[^>]+>")`, `_WS_RE =
     re.compile(r"\s+")`.
   - `def clean_text(s: str) -> str:` body in three lines —
     `s = html.unescape(s)`; `s = _TAG_RE.sub(" ", s)`;
     `return _WS_RE.sub(" ", s).strip()`.
   - No logging, no exception handling — pure function on `str`.

2. **Wire `clean_text` into `parse_entry`** in
   `backend/app/services/scraper.py`.
   - Add `from app.services.sanitize import clean_text` to the imports
     block.
   - In `parse_entry`, change:

     ```python
     title = (entry.get("title") or "").strip()
     description = (entry.get("summary") or "").strip()
     ```

     to apply `clean_text`:

     ```python
     title = clean_text(entry.get("title") or "")
     description = clean_text(entry.get("summary") or "")
     ```

   - Leave the `url` extraction line as-is: `url = (entry.get("link") or "").strip()`.
   - Leave the existing `if not title or not url or not description:
     return None` check unchanged — it already covers the "blank after
     clean" case, and the existing `scraper.entry.dropped` `WARNING` in
     `ingest_all` is already emitted once per `None` return (AC 6, AC 7,
     Decision #5).

3. **Write `backend/tests/unit/test_sanitize.py`.** Sync tests, no
   `pytest-asyncio` needed. One test function per behavior listed under
   "Unit tests required" below. Use plain `assert` and direct calls to
   `clean_text` — no fixtures, no mocks. Keep each test 1-3 lines.

4. **Extend `backend/tests/unit/test_scraper.py`.**
   - Add test cases under the existing `# --- parse_entry ---` section
     using the existing `_entry()` helper.
   - Cases to add (see "Unit tests required" below for exact names).
   - No new helpers required — `_entry()` already accepts `title=` and
     `summary=` kwargs.

5. **Run formatters and linters.** `cd backend && uv run black . && uv run
   ruff check .`. Both must pass with no new ignores (AC 14).

6. **Run the full backend unit suite.** `cd backend && uv run pytest
   tests/unit -v`. Must pass with the new tests included; the existing
   scraper tests must continue to pass (AC 13).

---

## Unit tests required

Test names below are stable contracts — QA audits coverage by name only.

### `backend/tests/unit/test_sanitize.py` (covers AC 11)

Each name maps unambiguously to one spec acceptance criterion or
explicitly-listed behavior:

- `test_clean_text_decodes_named_entity_amp` — input `"Apples &amp; oranges"`
  → `"Apples & oranges"` (AC 3, AC 11).
- `test_clean_text_decodes_numeric_entity_apostrophe` — input
  `"it&#39;s"` → `"it's"` (AC 2 numeric form, AC 3, AC 11).
- `test_clean_text_decodes_named_entity_nbsp` — input `"a&nbsp;b"` →
  asserts no `&nbsp;` substring remains and the two words are separated
  by a single ASCII space after collapse (AC 2 named form, AC 11).
- `test_clean_text_strips_paragraph_tag` — input `"<p>hi</p>"` → `"hi"`
  (AC 1, AC 11).
- `test_clean_text_strips_anchor_tag_with_attributes` — input
  `'<a href="http://x">link</a>'` → `"link"` (AC 1 with attributes, AC 11).
- `test_clean_text_strips_self_closing_img_tag` — input `'<img src="x"/>hi'`
  → `"hi"` (AC 1 self-closing, AC 11).
- `test_clean_text_strips_self_closing_br_tag` — input `"a<br/>b"` →
  asserts both `a` and `b` present and separated by whitespace (AC 1, AC 4,
  AC 11).
- `test_clean_text_does_not_fuse_words_across_tags` — input
  `"<p>Hello</p><p>world</p>"` → contains both `Hello` and `world` with
  whitespace between them (AC 4, AC 11).
- `test_clean_text_collapses_mixed_whitespace_runs` — input
  `"a \t\n  b"` → `"a b"` (AC 5, AC 11).
- `test_clean_text_strips_leading_and_trailing_whitespace` — input
  `"   hello   "` → `"hello"` (AC 5, AC 11).
- `test_clean_text_returns_empty_string_for_tag_only_input` — input
  `"<p></p>"` → `""` (AC 6 cleaner half, AC 11).
- `test_clean_text_returns_empty_string_for_entity_and_whitespace_only_input`
  — input `"&nbsp; \n"` → `""` (AC 6 cleaner half, AC 11).
- `test_clean_text_is_idempotent` — for each of several already-clean
  strings (`"hello"`, `"a b c"`, `"it's & more"`), `clean_text(s) == s`
  and `clean_text(clean_text(s)) == clean_text(s)` (AC 8, AC 11).
- `test_clean_text_module_imports_only_stdlib` — inspects
  `app.services.sanitize.__dict__` (or reads the module file) to assert
  no third-party imports — concretely, only `html` and `re` are imported
  from outside the package (AC 10, AC 11). Implemented by checking
  `inspect.getsource` for `import` lines.

### `backend/tests/unit/test_scraper.py` extensions (covers AC 12, AC 13)

- `test_parse_entry_cleans_html_in_title_and_description` — input entry
  with `title="Apples &amp; <b>oranges</b>"` and `summary="<p>hello
  world</p>"` produces an `Article` whose `title` contains no `<` or
  `&amp;` substring and whose `description` contains no `<` substring,
  and where the visible words (`Apples`, `oranges`, `hello`, `world`) are
  preserved (AC 12a, cross-references AC 1-5).
- `test_parse_entry_returns_none_for_tag_only_summary` — input entry
  with `summary="<p></p>"` returns `None` (AC 6 / AC 12b).
- `test_parse_entry_returns_none_for_tag_only_title` — input entry with
  `title="<br/><br/>"` returns `None` (AC 7).
- `test_parse_entry_preserves_url_query_and_fragment` — input entry with
  `link="https://example.com/path?a=1&b=2#frag"` produces an `Article`
  whose `url` is exactly that string (no entity decoding, no truncation
  at `&` or `#`) (AC 9).

The existing `test_ingest_all_logs_warning_for_dropped_entry` already
asserts the `scraper.entry.dropped` `WARNING` count, so AC 6 / AC 7's
"single WARNING per dropped entry" requirement is covered transitively
by `parse_entry` returning `None` and the unchanged dropped-log path in
`ingest_all`. No new `ingest_all` test is required.

---

## Definition of done

Derived 1-to-1 from spec acceptance criteria plus
[context.md](../../context.md) "Definition of Done".

- [ ] `backend/app/services/sanitize.py` exists with `clean_text(s: str) ->
      str` implementing unescape → tag-strip → whitespace-collapse, in that
      order, stdlib-only (AC 1, 2, 3, 4, 5, 8, 10).
- [ ] `parse_entry` calls `clean_text` on `title` and `summary`; `url` is
      untouched (AC 9).
- [ ] `parse_entry` returns `None` when `title` or `description` is empty
      after cleaning, and the existing `scraper.entry.dropped` `WARNING`
      fires exactly once per such dropped entry (AC 6, AC 7).
- [ ] `backend/tests/unit/test_sanitize.py` exists and all listed test
      functions pass under
      `cd backend && uv run pytest tests/unit/test_sanitize.py -v`
      (AC 11).
- [ ] `backend/tests/unit/test_scraper.py` carries the four new
      `parse_entry` tests listed above and passes under
      `cd backend && uv run pytest tests/unit/test_scraper.py -v` (AC 12).
- [ ] No regression: full unit suite green —
      `cd backend && uv run pytest tests/unit -v` (AC 13).
- [ ] No new third-party dependency: `backend/pyproject.toml` and
      `backend/uv.lock` unchanged (AC 10).
- [ ] `cd backend && uv run black .` and `cd backend && uv run ruff check
      .` both pass with no new `# noqa` markers (AC 14, context.md
      Standards).
- [ ] `tracker.md` row for `sanitize` updated to `in_qa` after
      implementation (post-`/start-dev`).
