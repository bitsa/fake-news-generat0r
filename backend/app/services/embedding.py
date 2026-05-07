import hashlib
import logging

from app.config import settings

log = logging.getLogger(__name__)

EMBEDDING_DIM: int = 1536


def _mock_embedding(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    needed = EMBEDDING_DIM
    out: list[float] = []
    chunk = digest
    while len(out) < needed:
        chunk = hashlib.sha256(chunk).digest()
        for byte in chunk:
            if len(out) >= needed:
                break
            out.append((byte - 127.5) / 127.5)
    return out


async def embed_text(text: str) -> list[float]:
    """Return a 1536-dim embedding. Hash-deterministic in mock mode."""
    if settings.openai_mock_mode:
        return _mock_embedding(text)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=settings.openai_request_timeout_seconds,
    )
    try:
        response = await client.embeddings.create(
            model=settings.openai_model_embedding,
            input=text,
        )
        log.info("embedding.ok model=%s", settings.openai_model_embedding)
        vector = list(response.data[0].embedding)
        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"Unexpected embedding dimension: got={len(vector)} expected={EMBEDDING_DIM}"
            )
        return vector
    except Exception as exc:
        log.error(
            "embedding.failed model=%s exc_type=%s",
            settings.openai_model_embedding,
            type(exc).__name__,
        )
        raise
