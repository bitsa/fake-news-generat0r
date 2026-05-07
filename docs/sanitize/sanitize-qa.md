# Sanitize Scraped Article Text — QA

Black-box coverage audit of [sanitize-spec.md](sanitize-spec.md) against the unit tests
the dev wrote. Tests are referenced by name only — no implementation logic was read.

Test files audited:

- [backend/tests/unit/test_sanitize.py](../../backend/tests/unit/test_sanitize.py)
- [backend/tests/unit/test_scraper.py](../../backend/tests/unit/test_scraper.py)

---

## Coverage Map

### AC 1 — No tags in stored title/description

- `test_sanitize.py::test_clean_text_strips_paragraph_tag`
- `test_sanitize.py::test_clean_text_strips_anchor_tag_with_attributes`
- `test_sanitize.py::test_clean_text_strips_self_closing_img_tag`
- `test_sanitize.py::test_clean_text_strips_self_closing_br_tag`
- `test_sanitize.py::test_clean_text_returns_empty_string_for_tag_only_input`
- `test_scraper.py::test_parse_entry_cleans_html_in_title_and_description`
  (asserts `"<" not in result.title` and `"<" not in result.description`)

### AC 2 — No HTML entities in stored title/description

- `test_sanitize.py::test_clean_text_decodes_named_entity_amp` (`&amp;`)
- `test_sanitize.py::test_clean_text_decodes_named_entity_nbsp` (`&nbsp;`)
- `test_sanitize.py::test_clean_text_decodes_numeric_entity_apostrophe` (`&#39;`)
- `test_scraper.py::test_parse_entry_cleans_html_in_title_and_description`
  (asserts `"&amp;" not in result.title`)

Partial coverage flag: the spec enumerates `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#39;`,
`&nbsp;`, plus hex character references of the form `&#xNN;`. Tests directly cover
`&amp;`, `&nbsp;`, and the decimal numeric form `&#39;`. They do not directly cover
`&lt;`, `&gt;`, `&quot;`, or the hex form `&#xNN;`. The dev's stdlib-only-imports
test (AC 10) and decision item 2 in the spec assert `html.unescape` covers all three
reference forms, so coverage is implicit; flagged as partial, not blocking.

### AC 3 — Entities decoded, not stripped

- `test_sanitize.py::test_clean_text_decodes_named_entity_amp`
  (`Apples &amp; oranges` → `Apples & oranges`, demonstrating decode-not-remove)
- `test_sanitize.py::test_clean_text_decodes_numeric_entity_apostrophe`
  (`it&#39;s` → `it's`)

The exact spec example (`&#8217;` right single quote) is not asserted, but the
decode-not-strip behavior is covered by the above two cases.

### AC 4 — Tag stripping does not fuse adjacent words

- `test_sanitize.py::test_clean_text_does_not_fuse_words_across_tags`
  (asserts `<p>Hello</p><p>world</p>` does not produce `Helloworld`)

### AC 5 — Whitespace collapsing

- `test_sanitize.py::test_clean_text_collapses_mixed_whitespace_runs`
  (mixed spaces/tabs/newlines collapsed to single space)
- `test_sanitize.py::test_clean_text_strips_leading_and_trailing_whitespace`

### AC 6 — Empty-after-clean drop (summary)

- `test_scraper.py::test_parse_entry_returns_none_for_tag_only_summary`
  (`<p></p>` → `None`)
- `test_scraper.py::test_parse_entry_returns_none_for_blank_description`
  (`"   "` → `None`)
- `test_scraper.py::test_ingest_all_logs_warning_for_dropped_entry`
  (verifies one `scraper.entry.dropped` WARNING per dropped entry)

Partial coverage flag: the existing dropped-entry log test triggers via a missing
title, not via a post-clean empty summary. The single-WARNING-per-dropped-entry
contract is asserted; that the same code path fires when the summary is dropped
specifically because it became empty after cleaning is not directly asserted.
Behaviorally coupled to AC 6's None return path; flagged as partial, not blocking.

### AC 7 — Empty title-after-clean drop

- `test_scraper.py::test_parse_entry_returns_none_for_tag_only_title`
  (`<br/><br/>` → `None`)
- `test_scraper.py::test_parse_entry_returns_none_for_blank_title`
- `test_scraper.py::test_ingest_all_logs_warning_for_dropped_entry`
  (single-WARNING-per-dropped-entry)

Same partial-coverage caveat as AC 6 regarding the post-clean dropped-warning path.

### AC 8 — Idempotent

- `test_sanitize.py::test_clean_text_is_idempotent`

### AC 9 — URL untouched by cleaning

- `test_scraper.py::test_parse_entry_preserves_url_query_and_fragment`
  (`https://example.com/path?a=1&b=2#frag` round-trips byte-exact)

### AC 10 — Stdlib only

- `test_sanitize.py::test_clean_text_module_imports_only_stdlib`
  (asserts module imports are exactly `import html` and `import re`)

Companion check (no new third-party dependency in `pyproject.toml` / `uv.lock`)
is verified by repository inspection during QA, not by a unit test.

### AC 11 — Unit tests for the cleaner exist and pass

Meta-criterion. Satisfied by the existence of
[backend/tests/unit/test_sanitize.py](../../backend/tests/unit/test_sanitize.py),
which covers all sub-items the spec enumerates:

- Entity decoding `&amp;` → `test_clean_text_decodes_named_entity_amp`
- Entity decoding `&#39;` → `test_clean_text_decodes_numeric_entity_apostrophe`
- Entity decoding `&nbsp;` → `test_clean_text_decodes_named_entity_nbsp`
- Tag stripping `<p>` → `test_clean_text_strips_paragraph_tag`
- Tag stripping `<a href="...">` → `test_clean_text_strips_anchor_tag_with_attributes`
- Tag stripping `<img/>` → `test_clean_text_strips_self_closing_img_tag`
- Tag stripping `<br/>` → `test_clean_text_strips_self_closing_br_tag`
- Whitespace across newlines/tabs → `test_clean_text_collapses_mixed_whitespace_runs`
- Empty result → `test_clean_text_returns_empty_string_for_tag_only_input`,
  `test_clean_text_returns_empty_string_for_entity_and_whitespace_only_input`
- Idempotence → `test_clean_text_is_idempotent`

Verified pass under
`cd backend && uv run pytest tests/unit/test_sanitize.py -v` at QA-run time.

### AC 12 — Unit tests for parse_entry HTML handling

- (a) HTML in title and summary, Article carries cleaned text →
  `test_scraper.py::test_parse_entry_cleans_html_in_title_and_description`
- (b) Summary is `"<p></p>"` → `parse_entry` returns `None` →
  `test_scraper.py::test_parse_entry_returns_none_for_tag_only_summary`

Verified pass under
`cd backend && uv run pytest tests/unit/test_scraper.py -v` at QA-run time.

### AC 13 — No regression to existing scraper acceptance criteria

The full pre-existing scraper test suite remains in place:

- `test_fetch_feed_passes_response_text_to_feedparser`
- `test_fetch_feed_caps_at_scrape_max_per_source` (entry cap)
- `test_parse_entry_returns_article_for_valid_entry`
- `test_parse_entry_returns_none_for_missing_title` /
  `..._missing_url` / `..._missing_description`
- `test_parse_entry_returns_none_for_blank_title` /
  `..._blank_url` / `..._blank_description`
- `test_ingest_all_fetches_all_three_sources` (source coverage)
- `test_ingest_all_commits_after_each_source` (per-source commit)
- `test_ingest_all_returns_inserted_articles_and_fetched_count`
- `test_ingest_all_uses_on_conflict_do_nothing` (idempotent upsert)
- `test_ingest_all_logs_warning_for_dropped_entry` (single WARNING on drop)
- `test_ingest_all_skips_failed_source_continues_others` (per-source error isolation)
- `test_ingest_all_logs_warning_per_failed_source`
- `test_ingest_all_raises_service_unavailable_when_all_sources_fail`

Pass/fail bound to the full `tests/unit/test_scraper.py` run.

### AC 14 — Backend lint and format pass

Not a unit test. QA verifies by running `ruff` and `black` against the modified
backend tree and confirming no errors and no new ignores or `# noqa` markers
introduced.

---

## Gap Analysis

No fully **UNCOVERED** acceptance criteria. Every AC has at least one mapped test
or a non-test verification step (AC 10 dependency check, AC 14 lint/format).

Two partial-coverage notes worth surfacing — the dev may choose to address them
before QA runs, but neither is a blocking hole given the behavior they cover is
implicitly tested:

- **AC 2** — `&lt;`, `&gt;`, `&quot;`, and the hex form `&#xNN;` are not directly
  decoded in any unit test. Coverage rests on the stdlib-imports test (AC 10) and
  spec decision 2.
- **AC 6 / AC 7** — the single-`scraper.entry.dropped` WARNING is asserted only
  for a missing-field dropped entry, not for an entry dropped specifically because
  cleaning emptied its title or summary.

---

## Pass / Fail Criteria

QA passes when both of the following hold:

1. Every acceptance criterion has at least one mapped test (or an explicit
   non-test verification, for AC 10's dependency check and AC 14's lint/format).
   Met above with two partial-coverage notes; no fully UNCOVERED criteria.
2. The mapped tests exit 0 with no failures and no skips.

Run, from repo root:

```bash
cd backend && uv run pytest -v \
  tests/unit/test_sanitize.py \
  tests/unit/test_scraper.py
```

Plus, for AC 10 and AC 14:

```bash
cd backend && uv run ruff check app tests
cd backend && uv run black --check app tests
git diff --name-only main... -- backend/pyproject.toml backend/uv.lock
```

(The last command must show no changes to `pyproject.toml` / `uv.lock` for AC 10.)
