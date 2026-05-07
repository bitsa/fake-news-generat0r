# QA — `chat-llm`

Black-box coverage audit. Maps each acceptance criterion in
[chat-llm-spec.md](chat-llm-spec.md) to the unit tests the dev wrote.
No new test code is proposed here.

## Coverage map

Test file paths are abbreviated below:

- **TCL** = `backend/tests/unit/test_chat_llm.py`
- **TCFG** = `backend/tests/test_config.py`

### Functional — real-call path

- **AC1** — exactly one streaming Chat Completions call per request:
  - TCL `test_real_call_invokes_chat_completions_create_exactly_once`
  - TCL `test_real_call_uses_chat_completions_create_with_stream_true_not_beta_parse`

- **AC2** — model / temperature / max_tokens / timeout wired from the right
  Settings fields; standard `chat.completions.create(stream=True)` surface,
  not `beta.chat.completions.parse`:
  - TCL `test_real_call_uses_openai_model_chat_setting`
  - TCL `test_real_call_uses_openai_temperature_chat_setting`
  - TCL `test_real_call_passes_chat_max_output_tokens_as_max_tokens`
  - TCL `test_real_call_passes_openai_request_timeout_seconds_to_client`
  - TCL `test_real_call_uses_chat_completions_create_with_stream_true_not_beta_parse`

- **AC3** — each non-empty `delta.content` emitted as a token SSE event;
  empty/whitespace deltas skipped; no chunk text dropped from final assistant
  content:
  - TCL `test_real_stream_emits_each_non_empty_delta_as_token_string`
  - TCL `test_real_stream_skips_empty_and_whitespace_only_deltas`
  - TCL `test_real_stream_concatenated_yielded_chunks_equal_full_assistant_text`
  - TCL `test_streaming_endpoint_commits_assistant_row_before_done_terminator_real_path`

- **AC4** — assistant row inserted with `role='assistant'`, `is_error=false`,
  `content` = concatenation of token texts, committed **before** `[DONE]`:
  - TCL `test_streaming_endpoint_commits_assistant_row_before_done_terminator_real_path`

- **AC5** — user row inserted with `role='user'`, `is_error=false`,
  `content` = request `message`, committed **before** any token event:
  - TCL `test_streaming_endpoint_commits_user_row_before_first_token_event_real_path`

### Functional — prompt construction

- **AC6** — message list ordered: one `system`, then history (oldest-first),
  then exactly one final `user`; system message is stable across runs:
  - TCL `test_prompt_builder_emits_system_then_history_then_final_user_message_in_order`
  - TCL `test_prompt_system_message_is_stable_across_runs_for_same_input`

- **AC7** — system/preamble includes original `title` + `description`;
  satirical `title` + `description` included when `ArticleFake` row exists
  and `transform_status='completed'`; only original when fake missing or
  pending:
  - TCL `test_prompt_builder_includes_original_article_title_and_description_in_system_message`
  - TCL `test_prompt_builder_includes_satirical_title_and_description_when_fake_completed`
  - TCL `test_prompt_builder_includes_only_original_when_fake_is_none`
  - TCL `test_prompt_builder_includes_only_original_when_fake_status_is_pending`

- **AC8** — history selection is chronological (`created_at` asc, tie-break
  by `id` asc); `assistant` rows with `is_error=true` are excluded:
  - TCL `test_prompt_builder_orders_history_chronologically_oldest_first_by_created_at_then_id`
  - TCL `test_prompt_builder_excludes_assistant_rows_with_is_error_true_from_history`

- **AC9** — when more than `chat_history_window` rows exist, only the most
  recent N are included, in chronological order:
  - TCL `test_prompt_builder_caps_history_at_chat_history_window_most_recent`

- **AC10** — newly received user message appears exactly once (the final
  `user` slot); the history slice does not double-count it:
  - TCL `test_prompt_builder_does_not_double_count_new_user_message_when_already_in_history`

### Functional — mock-mode path

- **AC11** — `CHAT_LLM_MOCK=true` produces the same wire output and
  persistence behaviour as Task 1's mock path; dispatch goes through the
  Task 1 `chat_mock` generator without router changes:
  - TCL `test_mock_mode_dispatches_to_chat_mock_generator_token_stream`
  - TCL `test_public_router_post_chat_url_status_codes_and_sse_format_unchanged_from_task_1`

- **AC12** — no network call; no `AsyncOpenAI` instantiation; works with a
  placeholder `OPENAI_API_KEY`:
  - TCL `test_mock_mode_does_not_instantiate_async_openai_client`
  - TCL `test_mock_mode_makes_no_call_to_chat_completions_create`
  - TCL `test_mock_mode_works_with_placeholder_openai_api_key`

### Functional — failure path

- **AC13** — on any failure: (a) one `is_error=true` assistant row whose
  `content` is the sentinel only; (b) one `data: {"error": ...}` SSE event
  with the sentinel; (c) no `[DONE]` after the error; (d) HTTP 200, no
  exception escapes; (e) one ERROR log with `article_id` and exception type
  name, no prompt/response/key. Variants required: timeout, API error,
  connection error, mid-stream:
  - (raise variants exercised at the `_stream_real_llm` boundary)
    - TCL `test_real_path_raises_on_timeout_so_streaming_service_can_persist_sentinel`
    - TCL `test_real_path_raises_on_openai_api_error`
    - TCL `test_real_path_raises_on_connection_error`
    - TCL `test_real_path_raises_on_mid_stream_exception_after_partial_tokens`
  - (a) TCL `test_streaming_endpoint_persists_assistant_row_with_sentinel_content_on_real_failure`
  - (b) TCL `test_streaming_endpoint_emits_single_error_event_with_sentinel_on_real_failure`
  - (c) TCL `test_streaming_endpoint_does_not_emit_done_after_real_failure`
  - (d) TCL `test_streaming_endpoint_returns_200_and_does_not_raise_on_real_failure`
  - (e) TCL `test_streaming_endpoint_logs_one_error_with_article_id_and_exc_type_name_on_real_failure`

- **AC14** — when failure occurs after some token events, persisted
  assistant `content` is the sentinel only (not the partial buffered tokens):
  - TCL `test_real_failure_after_partial_tokens_persisted_assistant_content_is_sentinel_only`

### Configuration / surface

- **AC15** — `chat_llm_mock` is a Pydantic Settings boolean defaulting to
  `true`:
  - TCFG `test_settings_chat_llm_mock_defaults_to_true`

- **AC16** — `chat_history_window` is a positive integer with default `10`:
  - TCFG `test_settings_chat_history_window_defaults_to_10`
  - TCFG `test_settings_chat_history_window_rejects_zero_or_negative`

- **AC17** — `chat_max_output_tokens` is a positive integer with default
  `512`:
  - TCFG `test_settings_chat_max_output_tokens_defaults_to_512`
  - TCFG `test_settings_chat_max_output_tokens_rejects_zero_or_negative`

- **AC18** — chat model / temperature reuse the existing
  `openai_model_chat` / `openai_temperature_chat` Settings fields; no
  parallel `chat_model` / `chat_temperature` fields are introduced:
  - TCFG `test_chat_llm_module_does_not_introduce_chat_model_or_chat_temperature_fields`

- **AC19** — `.env.example` documents the three new keys; pre-existing
  OpenAI lines are byte-identical to before this task:
  - TCFG `test_env_example_documents_chat_llm_mock`
  - TCFG `test_env_example_documents_chat_history_window`
  - TCFG `test_env_example_documents_chat_max_output_tokens`
  - TCFG `test_env_example_pre_existing_openai_keys_are_unchanged_by_chat_llm_task`

- **AC20** — public router contract unchanged from Task 1 (URL, request
  body shape, response media type, status codes, SSE event format):
  - TCL `test_public_router_post_chat_url_status_codes_and_sse_format_unchanged_from_task_1`

### Logging / safety

- **AC21** — no log line at any level contains user message, prompt body,
  full streamed response, or `OPENAI_API_KEY`:
  - TCL `test_no_log_record_emitted_during_real_streaming_contains_user_message_or_prompt_or_response_or_api_key`

- **AC22** — error sentinel is ≤ 80 chars, human-readable, and contains no
  provider error message, status codes, stack traces, or request IDs:
  - TCL `test_stream_failure_sentinel_is_short_human_readable_and_does_not_contain_provider_details`

### Quality gates

- **AC23** — backend `ruff` and `black` pass on touched files. Not a
  pytest unit test; enforced by lint tooling (`make lint` / CI). Verified
  during `/start-qa` by running the project's lint commands rather than
  via a mapped pytest case.

- **AC24** — backend unit tests pass with coverage of: prompt builder,
  real-call streaming with the SDK mocked, kill-switch short-circuit, and
  the timeout / API-error / connection-error / mid-stream variants of
  AC13. Meta-criterion satisfied when every mapped test under AC1–AC22
  exits 0 with no failures or skips.

- **AC25** — no test in the suite makes a real outbound OpenAI request.
  Convention-enforced: every real-path test in TCL uses
  `patch("openai.AsyncOpenAI", cls)` and patches a fake stream. There is
  no single mapped test asserting "the entire suite makes no network
  call"; coverage of this AC depends on the convention being held by every
  test that touches the real path. See gap analysis.

## Gap analysis

- **AC25 — no suite-wide assertion that no test performs a real outbound
  OpenAI request.** Each individual real-path test in `test_chat_llm.py`
  patches `openai.AsyncOpenAI`, but there is no fixture or test that
  guarantees the property at the suite level (e.g. an autouse fixture
  failing on real network egress, or a CI-level network sandbox check).
  This means the criterion is satisfied by convention only. Treating this
  as a **soft gap**: the per-test patching is consistent and the
  `chat_llm_mock=true` default further protects, so the property holds in
  practice — but no test would catch a regression where someone added a
  new real-path test and forgot to patch the SDK. Flagging for QA-phase
  decision: dev may either (a) accept the convention-only coverage and
  document it, or (b) add an autouse fixture that fails the test if
  `openai.AsyncOpenAI` is instantiated against a non-patched class.

No other gaps. Every other acceptance criterion (AC1–AC24) maps to at
least one named test on disk.

## Pass / fail criteria

QA passes when:

1. Every acceptance criterion has at least one mapped test (one soft gap
   on AC25 — see Gap analysis; pass requires an explicit decision on that
   item).
2. The mapped pytest cases below exit 0 with no failures and no skips.
3. AC23 lint gate passes: `ruff` and `black` clean on touched files.

Command to run the mapped tests:

```bash
cd backend && pytest -v \
  tests/unit/test_chat_llm.py \
  tests/test_config.py::test_settings_chat_llm_mock_defaults_to_true \
  tests/test_config.py::test_settings_chat_history_window_defaults_to_10 \
  tests/test_config.py::test_settings_chat_history_window_rejects_zero_or_negative \
  tests/test_config.py::test_settings_chat_max_output_tokens_defaults_to_512 \
  tests/test_config.py::test_settings_chat_max_output_tokens_rejects_zero_or_negative \
  tests/test_config.py::test_chat_llm_module_does_not_introduce_chat_model_or_chat_temperature_fields \
  tests/test_config.py::test_env_example_documents_chat_llm_mock \
  tests/test_config.py::test_env_example_documents_chat_history_window \
  tests/test_config.py::test_env_example_documents_chat_max_output_tokens \
  tests/test_config.py::test_env_example_pre_existing_openai_keys_are_unchanged_by_chat_llm_task
```

If the runner instead executes the full backend unit suite
(`pytest backend/tests/`), pass/fail applies to the full-suite result.

Lint gate (AC23):

```bash
cd backend && ruff check app/services/chat_llm.py app/config.py && \
  black --check app/services/chat_llm.py app/config.py
```

(Adjust the touched-file list if `/start-qa` discovers additional files
modified on the branch — black-box audit cannot enumerate them without
reading the dev doc.)
