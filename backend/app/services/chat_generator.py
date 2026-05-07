import asyncio
from collections.abc import AsyncIterator

from app.config import settings

MOCK_REPLY: str = (
    "This is a deterministic mock reply for the chat skeleton task — "
    "real LLM streaming arrives in the next iteration."
)

ERROR_SENTINEL: str = "chat stream failed"

_INTER_TOKEN_DELAY_SECONDS: float = 0.005


class _MockChatError(RuntimeError):
    """Raised by stream_mock_reply when the force-error sentinel matches."""


def _tokenize(reply: str) -> list[str]:
    parts = reply.split(" ")
    return [p + " " if i < len(parts) - 1 else p for i, p in enumerate(parts)]


_MOCK_CHUNKS: list[str] = _tokenize(MOCK_REPLY)
assert 10 <= len(_MOCK_CHUNKS) <= 20, "MOCK_REPLY must yield 10..20 chunks"
assert "".join(_MOCK_CHUNKS) == MOCK_REPLY


async def stream_mock_reply(message: str) -> AsyncIterator[str]:
    force_token = settings.chat_mock_force_error_token
    should_force_error = bool(force_token) and message == force_token

    for index, chunk in enumerate(_MOCK_CHUNKS):
        if should_force_error and index >= 1:
            raise _MockChatError("forced error via chat_mock_force_error_token")
        yield chunk
        await asyncio.sleep(_INTER_TOKEN_DELAY_SECONDS)
