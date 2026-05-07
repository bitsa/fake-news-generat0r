# chat-stream-skeleton Issue 02: AC8 verbatim user-row content intentionally relaxed by sanitize-on-ingest

**Task:** chat-stream-skeleton — Chat — POST streaming endpoint (mock LLM, real SSE)
**Spec criterion violated:** AC8: "...exactly one `chat_messages` row is inserted and committed for the request, with `article_id` matching the path param, `role='user'`, `is_error=false`, and `content` equal to the request body's `message` field verbatim."
**Severity:** medium
**Status:** open
**Found by:** /start-qa
**Date:** 2026-05-07

## What happened

The user row persisted by `post_chat_stream()` has
`content = clean_text(body.message)`, not `body.message`. Same root
cause as Issue 01 (sanitize-on-ingest at
[backend/app/services/chat.py:81-88](../../../backend/app/services/chat.py#L81-L88)).
Listed as a separate issue because AC8 is a separate spec line and
will need its own edit when the spec is amended.

The existing mapped test
`tests/routers/test_chat.py::test_post_chat_user_row_committed_before_stream_opens_with_verbatim_content`
still asserts `user_row.content == "verbatim msg"` and passes — but
only because the input string `"verbatim msg"` happens to be
sanitize-idempotent (no HTML, no whitespace runs). The test name
implies a stronger guarantee than the implementation actually
provides; if the input were `"  verbatim   msg  "` the test would
fail.

## What was expected

Spec [docs/chat-stream-skeleton/chat-stream-skeleton-spec.md](../chat-stream-skeleton-spec.md)
AC8 (lines 118-122) says `content` equals `body.message` verbatim.
Under the implemented behaviour it equals `clean_text(body.message)`.

## Reproduction steps

1. POST `/api/articles/{id}/chat` with body
   `{"message": "<i>hi</i>"}` against an existing article.
2. Read back via `GET /api/articles/{id}/chat`.
3. Observed: the user message row has `content == "hi"`.
   Spec-as-written expects `content == "<i>hi</i>"`.

Knock-on: AC10 ("user-then-assistant in chronological order with the
AC8/AC9 values") inherits the same drift on the `user` row's content
field. AC10 itself is otherwise satisfied (ordering, assistant-row
content) and is not separately filed.

## Environment

- Implementation: [backend/app/services/chat.py:81-91](../../../backend/app/services/chat.py#L81-L91)
- Mapped test that masks the drift (PASSED, but inadvertently):
  - `tests/routers/test_chat.py::test_post_chat_user_row_committed_before_stream_opens_with_verbatim_content`
- Knock-on AC10 mapped test (PASSED, fixture content sanitize-idempotent):
  - `tests/routers/test_chat.py::test_get_chat_history_after_happy_post_returns_user_then_assistant_in_order`

## Suggested next action

Clarify spec — see Issue 01. The same spec amendment that updates AC2
should update AC8 to read `content = clean_text(body.message)`, with
AC10 inheriting the change implicitly. Optionally rename
`test_post_chat_user_row_committed_before_stream_opens_with_verbatim_content`
once the spec is amended so the test name no longer overstates the
guarantee — but that is a follow-up nicety, not a blocker.

Note on AC17 (force-error exact-match): the comparison inside
`stream_mock_reply` is against the SANITIZED message. So a request
with `message="<b>boom</b>"` and
`CHAT_MOCK_FORCE_ERROR_TOKEN="boom"` WILL match. The dev hand-off
flagged this as intentional and the QA doc's existing
`test_stream_mock_reply_raises_when_message_exactly_equals_force_token`
remains valid (it tests against `"boom"` directly, post-sanitize
identity). No separate issue is filed for AC17 — recording the
sanitize-after-the-fact comparison semantics here for the spec
edit.
