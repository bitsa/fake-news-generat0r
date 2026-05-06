import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.config import settings
from app.services import openai_transform
from app.services.openai_transform import (
    MOCK_DESCRIPTION,
    MOCK_TITLE,
    SatiricalPair,
    generate_satirical,
)


def _make_completion(parsed: SatiricalPair | None, refusal: object | None = None):
    message = MagicMock()
    message.parsed = parsed
    message.refusal = refusal
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _make_async_openai(parse_return=None, parse_side_effect=None):
    """Build an AsyncOpenAI class mock and return (cls, parse_mock, instance)."""
    parse_mock = AsyncMock()
    if parse_side_effect is not None:
        parse_mock.side_effect = parse_side_effect
    else:
        parse_mock.return_value = parse_return
    instance = MagicMock()
    instance.beta.chat.completions.parse = parse_mock
    cls = MagicMock(return_value=instance)
    return cls, parse_mock, instance


# ---------------------------------------------------------------------------
# Real-mode path
# ---------------------------------------------------------------------------


async def test_generate_satirical_calls_openai_once_with_original_title_and_description(
    monkeypatch,
):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    parsed = SatiricalPair(title="Sat title", description="Sat description")
    cls, parse_mock, _ = _make_async_openai(parse_return=_make_completion(parsed))

    with patch("openai.AsyncOpenAI", cls):
        result = await generate_satirical("Original T", "Original D")

    assert result == parsed
    parse_mock.assert_awaited_once()
    kwargs = parse_mock.await_args.kwargs
    messages = kwargs["messages"]
    user_text = next(m["content"] for m in messages if m["role"] == "user")
    assert "Original T" in user_text
    assert "Original D" in user_text


async def test_generate_satirical_returns_response_title_and_description_on_success(
    monkeypatch,
):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    parsed = SatiricalPair(title="Sat title", description="Sat description")
    cls, _, _ = _make_async_openai(parse_return=_make_completion(parsed))

    with patch("openai.AsyncOpenAI", cls):
        result = await generate_satirical("orig t", "orig d")

    assert result.title == "Sat title"
    assert result.description == "Sat description"


async def test_generate_satirical_returned_title_and_description_are_non_empty_and_distinct_from_originals_and_mocks(  # noqa: E501
    monkeypatch,
):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    parsed = SatiricalPair(title="Distinct title", description="Distinct desc")
    cls, _, _ = _make_async_openai(parse_return=_make_completion(parsed))

    with patch("openai.AsyncOpenAI", cls):
        result = await generate_satirical("the original title", "the original desc")

    assert result.title and result.description
    assert result.title != "the original title"
    assert result.description != "the original desc"
    assert result.title != MOCK_TITLE
    assert result.description != MOCK_DESCRIPTION


async def test_generate_satirical_uses_structured_output_response_format(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    parsed = SatiricalPair(title="t", description="d")
    cls, parse_mock, _ = _make_async_openai(parse_return=_make_completion(parsed))

    with patch("openai.AsyncOpenAI", cls):
        await generate_satirical("a", "b")

    kwargs = parse_mock.await_args.kwargs
    assert kwargs["response_format"] is SatiricalPair


async def test_generate_satirical_passes_request_timeout_setting_to_openai_client(
    monkeypatch,
):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    monkeypatch.setattr(settings, "openai_request_timeout_seconds", 17)
    parsed = SatiricalPair(title="t", description="d")
    cls, _, _ = _make_async_openai(parse_return=_make_completion(parsed))

    with patch("openai.AsyncOpenAI", cls):
        await generate_satirical("a", "b")

    cls.assert_called_once()
    assert cls.call_args.kwargs["timeout"] == 17


async def test_generate_satirical_uses_settings_model_and_temperature(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    monkeypatch.setattr(settings, "openai_model_transform", "test-model-x")
    monkeypatch.setattr(settings, "openai_temperature_transform", 0.42)
    parsed = SatiricalPair(title="t", description="d")
    cls, parse_mock, _ = _make_async_openai(parse_return=_make_completion(parsed))

    with patch("openai.AsyncOpenAI", cls):
        await generate_satirical("a", "b")

    kwargs = parse_mock.await_args.kwargs
    assert kwargs["model"] == "test-model-x"
    assert kwargs["temperature"] == 0.42


# ---------------------------------------------------------------------------
# Mock-mode path
# ---------------------------------------------------------------------------


async def test_generate_satirical_mock_mode_returns_canonical_pair(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", True)

    result = await generate_satirical("anything", "anything else")

    assert result.title == MOCK_TITLE
    assert result.description == MOCK_DESCRIPTION


async def test_generate_satirical_mock_mode_does_not_instantiate_openai_client(
    monkeypatch,
):
    monkeypatch.setattr(settings, "openai_mock_mode", True)
    cls, _, _ = _make_async_openai(parse_return=_make_completion(None))

    with patch("openai.AsyncOpenAI", cls):
        await generate_satirical("a", "b")

    cls.assert_not_called()


async def test_generate_satirical_mock_mode_makes_no_network_request(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", True)
    cls, parse_mock, _ = _make_async_openai(parse_return=_make_completion(None))

    with patch("openai.AsyncOpenAI", cls):
        await generate_satirical("a", "b")

    parse_mock.assert_not_called()


async def test_generate_satirical_mock_mode_works_with_placeholder_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", True)
    monkeypatch.setattr(settings, "openai_api_key", "sk-fake-placeholder")

    result = await generate_satirical("a", "b")

    assert result.title == MOCK_TITLE


# ---------------------------------------------------------------------------
# Failure variants — propagated to caller
# ---------------------------------------------------------------------------


async def test_generate_satirical_propagates_timeout_exception(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    cls, _, _ = _make_async_openai(parse_side_effect=TimeoutError("timed out"))

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(TimeoutError):
            await generate_satirical("a", "b")


async def test_generate_satirical_propagates_api_error_exception(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)

    class FakeAPIError(Exception):
        pass

    cls, _, _ = _make_async_openai(parse_side_effect=FakeAPIError("rate limited"))

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(FakeAPIError):
            await generate_satirical("a", "b")


async def test_generate_satirical_propagates_malformed_json_exception(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    cls, _, _ = _make_async_openai(
        parse_side_effect=json.JSONDecodeError("bad json", "doc", 0)
    )

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(json.JSONDecodeError):
            await generate_satirical("a", "b")


async def test_generate_satirical_propagates_schema_validation_exception(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)

    try:
        SatiricalPair(title=None)  # type: ignore[arg-type]
    except ValidationError as built:
        validation_error = built

    cls, _, _ = _make_async_openai(parse_side_effect=validation_error)

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(ValidationError):
            await generate_satirical("a", "b")


async def test_generate_satirical_raises_on_refusal_response(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    completion = _make_completion(parsed=None, refusal="I cannot help with that")
    cls, _, _ = _make_async_openai(parse_return=completion)

    with patch("openai.AsyncOpenAI", cls):
        with pytest.raises(ValueError):
            await generate_satirical("a", "b")


# ---------------------------------------------------------------------------
# Service-side failure logging (AC14 safety, scoped to app.services.openai_transform)
# ---------------------------------------------------------------------------


async def test_generate_satirical_failure_emits_one_error_log_with_model_and_exc_type(
    monkeypatch, caplog
):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    monkeypatch.setattr(settings, "openai_model_transform", "test-model-x")
    cls, _, _ = _make_async_openai(parse_side_effect=TimeoutError("timed out"))

    with patch("openai.AsyncOpenAI", cls):
        with caplog.at_level(logging.ERROR, logger="app.services.openai_transform"):
            with pytest.raises(TimeoutError):
                await generate_satirical("a", "b")

    error_records = [
        r for r in caplog.records if r.name == "app.services.openai_transform"
    ]
    assert len(error_records) == 1
    msg = error_records[0].getMessage()
    assert "test-model-x" in msg
    assert "TimeoutError" in msg


async def test_generate_satirical_failure_log_does_not_contain_prompt_response_or_api_key(  # noqa: E501
    monkeypatch, caplog
):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    monkeypatch.setattr(settings, "openai_api_key", "sk-secret-do-not-leak")
    secret_title = "SECRET-ORIGINAL-TITLE-XYZ"
    secret_desc = "SECRET-ORIGINAL-DESCRIPTION-XYZ"
    cls, _, _ = _make_async_openai(parse_side_effect=RuntimeError("boom"))

    with patch("openai.AsyncOpenAI", cls):
        with caplog.at_level(logging.DEBUG, logger="app.services.openai_transform"):
            with pytest.raises(RuntimeError):
                await generate_satirical(secret_title, secret_desc)

    for record in caplog.records:
        if record.name != "app.services.openai_transform":
            continue
        msg = record.getMessage()
        assert secret_title not in msg
        assert secret_desc not in msg
        assert "sk-secret-do-not-leak" not in msg
        assert "rewrite news articles" not in msg  # system prompt fragment


# ---------------------------------------------------------------------------
# Module export sanity (constants moved from worker → service)
# ---------------------------------------------------------------------------


def test_openai_transform_module_exposes_mock_constants():
    assert isinstance(openai_transform.MOCK_TITLE, str) and openai_transform.MOCK_TITLE
    assert (
        isinstance(openai_transform.MOCK_DESCRIPTION, str)
        and openai_transform.MOCK_DESCRIPTION
    )
