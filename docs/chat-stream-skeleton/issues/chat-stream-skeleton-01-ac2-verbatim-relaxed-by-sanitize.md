# chat-stream-skeleton Issue 01: AC2 verbatim sub-criterion intentionally relaxed by sanitize-on-ingest

**Task:** chat-stream-skeleton — Chat — POST streaming endpoint (mock LLM, real SSE)
**Spec criterion violated:** AC2, last sentence: "No transformation is applied to the stored `content` — the original `message` is persisted verbatim, leading/trailing whitespace included, provided it passes validation."
**Severity:** medium
**Status:** open
**Found by:** /start-qa
**Date:** 2026-05-07

## What happened

`post_chat_stream()` in `backend/app/services/chat.py` calls
`clean_text()` from `app.services.sanitize` on `body.message` BEFORE
persisting the `user` row and BEFORE handing the message to the mock
generator. `clean_text()` HTML-decodes, strips tags, collapses runs of
whitespace to single spaces, and trims. As a result, the persisted
`chat_messages.content` for a `user` row is `clean_text(body.message)`,
not `body.message` verbatim.

This is a deliberate mid-implementation change (see the TODO block at
`backend/app/services/chat.py:16-24`) to avoid persisting raw HTML / tag
soup and to avoid forwarding obviously-malformed payloads to the
LLM call site. The dev hand-off explicitly flagged it as drift to be
paper-trailed for the spec update.

## What was expected

Spec [docs/chat-stream-skeleton/chat-stream-skeleton-spec.md](../chat-stream-skeleton-spec.md)
AC2 (line 91) requires verbatim persistence of `body.message`,
including leading / trailing whitespace, once validation passes. Under
that wording, an input of `"  hello   world  "` should persist exactly
`"  hello   world  "`. Under the implemented behaviour it persists
`"hello world"`.

## Reproduction steps

1. POST `/api/articles/{id}/chat` with body
   `{"message": "  hello   world  "}` against an existing article.
2. Inspect the inserted `chat_messages` row for `role='user'`.
3. Observed: `content == "hello world"` (whitespace collapsed, ends
   trimmed). Spec-as-written expects `content == "  hello   world  "`.

A second reproduction: POST
`{"message": "click <a href='x'>here</a> &amp; win"}`. Observed
persisted content has tags stripped and `&amp;` HTML-decoded; spec
expects byte-equal persistence of the raw string.

QA doc coverage-map note: the QA doc lists two tests for this AC2
sub-criterion that do not exist in the test files —
`tests/routers/test_chat.py::test_post_chat_persists_message_verbatim_including_surrounding_whitespace`
and
`tests/unit/test_chat_service.py::test_post_chat_stream_persists_message_verbatim`.
They were presumably planned before the sanitize-on-ingest change
landed and were silently dropped (a verbatim-whitespace assertion
would now fail). The behaviour the dev actually shipped is instead
covered by `test_post_chat_sanitizes_user_message_before_persisting`,
`test_post_chat_strips_html_tags_from_user_message_before_persisting`
(router-level) and the equivalent `test_chat_service.py::*` pair —
all green.

## Environment

- Implementation: [backend/app/services/chat.py:81-88](../../../backend/app/services/chat.py#L81-L88)
- Sanitizer: [backend/app/services/sanitize.py](../../../backend/app/services/sanitize.py)
- Mapped tests for the relaxed-behaviour AC-SAN-1 (all PASSED in QA run):
  - `tests/routers/test_chat.py::test_post_chat_sanitizes_user_message_before_persisting`
  - `tests/routers/test_chat.py::test_post_chat_strips_html_tags_from_user_message_before_persisting`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_sanitizes_message_before_persisting`
  - `tests/unit/test_chat_service.py::test_post_chat_stream_strips_html_tags_from_user_message`

## Suggested next action

Clarify spec — acceptance criterion ambiguous; needs human decision.

Specifically: amend AC2 in
[chat-stream-skeleton-spec.md](../chat-stream-skeleton-spec.md) to
state that `content` is `clean_text(body.message)` rather than verbatim
`body.message`, and add the two new sub-criteria the dev hand-off
proposed:

- **AC-SAN-1**: HTML tags / entities stripped, whitespace collapsed
  before persistence and before the generator is invoked.
- **AC-SAN-2**: empty post-sanitize input (e.g. `"<p></p>"`,
  `"&nbsp;"`) → HTTP 422 via `ValidationError`, no rows written.

Both are already covered by tests and pass green; the spec doc is the
only artefact out of date.
