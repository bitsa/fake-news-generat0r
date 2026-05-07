import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.services.embedding import EMBEDDING_DIM, embed_text


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", True)


async def test_embed_text_mock_does_not_import_openai_client(monkeypatch):
    def _explode(*args, **kwargs):
        raise AssertionError("openai client must not be instantiated in mock mode")

    with patch("openai.AsyncOpenAI", side_effect=_explode):
        result = await embed_text("hello")
    assert len(result) == EMBEDDING_DIM


async def test_embed_text_mock_returns_length_1536():
    result = await embed_text("any input text")
    assert len(result) == 1536


async def test_embed_text_mock_same_input_returns_identical_vector():
    a = await embed_text("identical input")
    b = await embed_text("identical input")
    assert a == b


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


async def test_embed_text_mock_different_inputs_have_cosine_strictly_less_than_one():
    a = await embed_text("first text")
    b = await embed_text("second text")
    assert _cos(a, b) < 1.0


async def test_embed_text_real_path_calls_openai_with_configured_model(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", False)
    monkeypatch.setattr(settings, "openai_model_embedding", "test-embedding-model")

    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1] * 1536)]

    fake_client = MagicMock()
    fake_client.embeddings = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=fake_response)

    with patch("openai.AsyncOpenAI", return_value=fake_client) as ctor:
        result = await embed_text("input")

    ctor.assert_called_once()
    fake_client.embeddings.create.assert_awaited_once_with(
        model="test-embedding-model", input="input"
    )
    assert len(result) == 1536
