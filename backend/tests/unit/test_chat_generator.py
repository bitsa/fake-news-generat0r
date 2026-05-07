import sys
import time
from unittest.mock import patch

import pytest

from app.config import settings
from app.services import chat_generator
from app.services.chat_generator import MOCK_REPLY, stream_mock_reply


async def _collect(message: str) -> list[str]:
    return [chunk async for chunk in stream_mock_reply(message)]


# AC14 — deterministic, finite, 10..20 chunks


async def test_stream_mock_reply_yields_between_10_and_20_chunks_inclusive():
    chunks = await _collect("hello")
    assert 10 <= len(chunks) <= 20


async def test_stream_mock_reply_concatenates_to_canonical_string():
    chunks = await _collect("hello")
    assert "".join(chunks) == MOCK_REPLY


async def test_stream_mock_reply_is_deterministic_across_calls():
    a = await _collect("first")
    b = await _collect("second")
    assert a == b


# AC15 — strictly positive total duration


async def test_stream_mock_reply_has_strictly_positive_total_duration():
    start = time.perf_counter()
    await _collect("hello")
    elapsed = time.perf_counter() - start
    assert elapsed > 0.0


# AC16 — no OpenAI SDK import / no outbound HTTP


async def test_stream_mock_reply_does_not_import_openai_sdk_module():
    pre_loaded = "openai" in sys.modules
    if not pre_loaded:
        await _collect("hello")
        assert "openai" not in sys.modules


async def test_stream_mock_reply_makes_no_outbound_http_call():
    with patch("httpx.AsyncClient.send") as send_spy:
        chunks = await _collect("hello")
    assert chunks
    assert send_spy.call_count == 0


# AC17 — exact-match force-error semantics


async def test_stream_mock_reply_raises_when_message_exactly_equals_force_token():
    with patch.object(settings, "chat_mock_force_error_token", "boom"):
        with pytest.raises(chat_generator._MockChatError):
            async for _ in stream_mock_reply("boom"):
                pass


async def test_stream_mock_reply_does_not_raise_on_substring_match_of_force_token():
    with patch.object(settings, "chat_mock_force_error_token", "boom"):
        chunks = [c async for c in stream_mock_reply("boomerang")]
    assert "".join(chunks) == MOCK_REPLY


async def test_stream_mock_reply_does_not_raise_on_case_insensitive_match():
    with patch.object(settings, "chat_mock_force_error_token", "boom"):
        chunks = [c async for c in stream_mock_reply("BOOM")]
    assert "".join(chunks) == MOCK_REPLY


async def test_stream_mock_reply_does_not_raise_on_whitespace_trimmed_match():
    with patch.object(settings, "chat_mock_force_error_token", "boom"):
        chunks = [c async for c in stream_mock_reply(" boom ")]
    assert "".join(chunks) == MOCK_REPLY


async def test_stream_mock_reply_does_not_raise_when_force_token_is_none_default():
    with patch.object(settings, "chat_mock_force_error_token", None):
        chunks = [c async for c in stream_mock_reply("boom")]
    assert "".join(chunks) == MOCK_REPLY


# AC18 / AC19 — settings defaults


def test_settings_chat_message_max_chars_default_is_512():
    assert settings.chat_message_max_chars == 512


def test_settings_chat_mock_force_error_token_default_is_none():
    assert settings.chat_mock_force_error_token is None
