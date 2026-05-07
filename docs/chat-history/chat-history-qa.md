# Chat History Endpoint QA

Black-box coverage audit for the acceptance criteria in
[chat-history-spec.md](chat-history-spec.md). Maps each criterion to the unit
tests on disk; does not introduce new tests.

## Coverage map

| # | Acceptance criterion | Mapped tests |
|---|---|---|
| 1 | Migration applies cleanly; new revision's `down_revision` is `cfe2a836394a`. | `backend/tests/unit/test_chat_migration.py::test_chat_migration_down_revision_is_genesis`, `backend/tests/unit/test_chat_migration.py::test_chat_migration_upgrade_creates_chat_messages_table_and_index`, `backend/tests/unit/test_chat_migration.py::test_chat_migration_upgrade_and_downgrade_callable` |
| 2 | Migration is reversible — downgrade drops table and index. | `backend/tests/unit/test_chat_migration.py::test_chat_migration_downgrade_drops_chat_messages_table_and_index`, `backend/tests/unit/test_chat_migration.py::test_chat_migration_upgrade_and_downgrade_callable` |
| 3 | `chat_messages` table shape — columns, types, nullability, FK with `ON DELETE CASCADE`, server defaults. | `backend/tests/unit/test_chat_models.py::test_chat_message_table_columns_match_spec`, `backend/tests/unit/test_chat_models.py::test_chat_message_is_error_server_default_false_and_created_at_default_now`, `backend/tests/unit/test_chat_models.py::test_chat_message_request_id_nullable_and_no_unique_constraint`, `backend/tests/unit/test_chat_models.py::test_chat_message_article_id_fk_cascade_delete` |
| 4 | Role check constraint named `ck_chat_messages_role` rejects values other than `'user'`/`'assistant'`. | `backend/tests/unit/test_chat_models.py::test_chat_message_role_check_constraint_rejects_other_values`, `backend/tests/unit/test_chat_migration.py::test_chat_migration_role_check_constraint_named_and_lists_both_roles` |
| 5 | Composite index `ix_chat_messages_article_id_created_at` on `(article_id, created_at)`. | `backend/tests/unit/test_chat_models.py::test_chat_message_composite_index_on_article_id_and_created_at`, `backend/tests/unit/test_chat_migration.py::test_chat_migration_upgrade_creates_chat_messages_table_and_index` |
| 6 | Server defaults populate on insert (`is_error=false`, `created_at=now()`). | `backend/tests/unit/test_chat_models.py::test_chat_message_is_error_server_default_false_and_created_at_default_now` |
| 7 | `request_id` accepts NULL (no unique constraint). | `backend/tests/unit/test_chat_models.py::test_chat_message_request_id_nullable_and_no_unique_constraint` |
| 8 | Cascade delete — deleting `articles` row removes associated `chat_messages`. | `backend/tests/unit/test_chat_models.py::test_chat_message_article_id_fk_cascade_delete` |
| 9 | Endpoint registered under `/api` (`/api/articles/{article_id}/chat`). | `backend/tests/routers/test_chat.py::test_get_chat_history_registered_under_api_prefix` |
| 10 | Happy path returns ordered history (user then assistant). | `backend/tests/unit/test_chat_service.py::test_chat_service_returns_messages_in_chronological_order` |
| 11 | Empty history for existing article returns `200` with `messages: []`. | `backend/tests/unit/test_chat_service.py::test_chat_service_returns_empty_messages_for_article_with_no_messages` |
| 12 | 404 for missing article with body `{"detail": "Article {id} not found"}` via `NotFoundError`. | `backend/tests/unit/test_chat_service.py::test_chat_service_raises_not_found_error_for_missing_article`, `backend/tests/routers/test_chat.py::test_get_chat_history_returns_404_with_detail_for_missing_article` |
| 13 | Stable tie-break on identical `created_at` — orders by ascending `id`. | `backend/tests/unit/test_chat_service.py::test_chat_service_tie_break_orders_identical_created_at_by_ascending_id` |
| 14 | Response shape — top level has exactly two keys (`article_id`, `messages`). | `backend/tests/routers/test_chat.py::test_get_chat_history_response_shape_has_exactly_two_top_level_keys` |
| 15 | Response shape — each message has exactly six keys (`id`, `role`, `content`, `is_error`, `request_id`, `created_at`). | `backend/tests/routers/test_chat.py::test_get_chat_history_each_message_has_exactly_six_required_keys` |
| 16 | `is_error` exposed in response and defaults `false`. | `backend/tests/routers/test_chat.py::test_get_chat_history_is_error_field_defaults_false_in_response` |
| 17 | `request_id` exposed in response and may be `null`. | `backend/tests/routers/test_chat.py::test_get_chat_history_request_id_field_may_be_null_in_response` |
| 18 | `created_at` serialised as ISO 8601 with timezone (`Z` or `+00:00`). | `backend/tests/routers/test_chat.py::test_get_chat_history_created_at_serialised_iso8601_with_timezone` |
| 19 | No auth required — endpoint returns `200` without credentials. | `backend/tests/routers/test_chat.py::test_get_chat_history_no_auth_required_returns_200` |
| 20 | POST not implemented — `POST /api/articles/{article_id}/chat` returns `405`. | `backend/tests/routers/test_chat.py::test_get_chat_history_post_method_returns_405_method_not_allowed` |

## Gap analysis

No gaps. Every acceptance criterion has at least one mapped test.

Notes for QA execution (not gaps, scope clarifications):

- Criteria 1, 2, 4, 6, 8 are verified at the unit-test layer by inspecting
  migration source / SQLAlchemy metadata (constraints, FK `ondelete`, server
  defaults, named index/check constraint). Real DB upgrade/downgrade rounds
  and live `INSERT … role='system'` integrity errors are integration-level
  concerns out of scope for unit tests. The unit suite asserts the schema
  *declares* the behavior; live enforcement is left to the integration/smoke
  suite.

## Pass / fail criteria

QA passes when:

1. Every acceptance criterion has at least one mapped test (zero UNCOVERED) — currently met.
2. The mapped tests exit `0` with no failures and no skips.

Run the mapped tests with:

```bash
pytest -v \
  backend/tests/unit/test_chat_migration.py \
  backend/tests/unit/test_chat_models.py \
  backend/tests/unit/test_chat_service.py \
  backend/tests/routers/test_chat.py
```
