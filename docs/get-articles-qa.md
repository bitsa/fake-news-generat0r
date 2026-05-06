# GET /api/articles QA

Black-box coverage audit for the acceptance criteria in
[get-articles-spec.md](get-articles-spec.md). Maps each criterion to the unit
tests on disk; does not introduce new tests.

## Coverage map

| # | Acceptance criterion | Mapped tests |
|---|---|---|
| 1 | Happy path — completed pair returned with `total: 1`, `pending: 0`, one element. | `backend/tests/routers/test_articles.py::test_get_articles_happy_path_completed_pair_returns_200` |
| 2 | Pending fake excluded from `articles`, counted in `pending`. | `backend/tests/routers/test_articles.py::test_get_articles_pending_fake_excluded_from_articles_counted_in_pending` |
| 3 | Article with no fake row excluded from `articles` and not in `pending`. | `backend/tests/routers/test_articles.py::test_get_articles_no_fake_article_excluded_from_articles_and_not_in_pending` |
| 4 | `total` counts all articles regardless of fake status. | `backend/tests/routers/test_articles.py::test_get_articles_total_counts_all_articles_regardless_of_fake_status` |
| 5 | `pending` counts only `transform_status = 'pending'` rows. | `backend/tests/routers/test_articles.py::test_get_articles_pending_counts_only_pending_fakes` |
| 6 | Empty DB returns `{"total": 0, "pending": 0, "articles": []}` with `200`. | `backend/tests/routers/test_articles.py::test_get_articles_empty_db_returns_200_with_zeros_and_empty_array` |
| 7 | Ordering: later `published_at` first; `NULL` last. | `backend/tests/unit/test_articles_service.py::test_get_articles_service_ordering_later_published_at_appears_first`, `backend/tests/unit/test_articles_service.py::test_get_articles_service_null_published_at_appears_after_dated_articles` |
| 8 | Response top-level has exactly three keys: `total`, `pending`, `articles`. | `backend/tests/routers/test_articles.py::test_get_articles_response_shape_has_exactly_three_top_level_keys` |
| 9 | Each pair has `id`, `article` (with required fields), `fake` (with required fields); `id == article.id == fake.id`. | `backend/tests/routers/test_articles.py::test_get_articles_each_pair_has_id_article_and_fake_with_all_required_fields`, `backend/tests/unit/test_articles_service.py::test_get_articles_service_fake_id_equals_article_id` |
| 10 | Nullable fields (`article.description`, `article.published_at`, `fake.title`, `fake.description`, `fake.model`, `fake.temperature`) may be `null`; `fake.created_at` always present. | `backend/tests/routers/test_articles.py::test_get_articles_nullable_fields_may_be_null_in_both_article_and_fake` |
| 11 | `article.source` serialised as enum string value (`"NYT"`, `"NPR"`, `"Guardian"`), not index. | `backend/tests/routers/test_articles.py::test_get_articles_source_field_serialised_as_string_value_not_enum_index` |
| 12 | Datetime fields serialised as ISO 8601 with timezone. | `backend/tests/routers/test_articles.py::test_get_articles_datetime_fields_serialised_as_iso8601_with_timezone` |
| 13 | No auth required — unauthenticated request returns `200`. | `backend/tests/routers/test_articles.py::test_get_articles_no_auth_required_returns_200` |
| 14 | Registered under `/api` prefix; `/articles` (unprefixed) is `404`. | `backend/tests/routers/test_articles.py::test_get_articles_registered_under_api_prefix` |

## Gap analysis

No gaps. Every acceptance criterion has at least one mapped test.

## Pass / fail criteria

QA passes when:

1. Every acceptance criterion has at least one mapped test (zero UNCOVERED) — currently met.
2. The mapped tests exit `0` with no failures and no skips.

Run the mapped tests with:

```bash
pytest -v \
  backend/tests/routers/test_articles.py \
  backend/tests/unit/test_articles_service.py
```
