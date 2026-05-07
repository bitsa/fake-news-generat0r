import math
import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import ArticleEmbedding
from app.services.embedding import embed_text

STOPWORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "at", "is"}
)

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def tokenize(title: str) -> set[str]:
    lowered = title.lower()
    cleaned = _PUNCT_RE.sub(" ", lowered)
    tokens = cleaned.split()
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


@dataclass
class Incumbent:
    article_id: int
    tokens: set[str]
    text: str
    embedding: list[float] | None = None


@dataclass
class DedupDecision:
    accept: bool
    reason: str | None
    matched_article_id: int | None
    candidate_embedding: list[float] | None
    embedding_calls: int


async def find_near_duplicate(
    session: AsyncSession,
    candidate_title: str,
    candidate_text: str,
    incumbents: list[Incumbent],
) -> DedupDecision:
    cand_tokens = tokenize(candidate_title)

    high = settings.dedup_jaccard_high
    floor = settings.dedup_jaccard_floor
    cosine_threshold = settings.dedup_cosine_threshold

    j_max = -1.0
    j_argmax: Incumbent | None = None
    escalation: list[tuple[Incumbent, float]] = []

    for inc in incumbents:
        j = _jaccard(cand_tokens, inc.tokens)
        if j > j_max:
            j_max = j
            j_argmax = inc
        if j >= floor:
            escalation.append((inc, j))

    if j_argmax is not None and j_max >= high:
        return DedupDecision(
            accept=False,
            reason="jaccard",
            matched_article_id=j_argmax.article_id,
            candidate_embedding=None,
            embedding_calls=0,
        )

    if not escalation:
        return DedupDecision(
            accept=True,
            reason=None,
            matched_article_id=None,
            candidate_embedding=None,
            embedding_calls=0,
        )

    embedding_calls = 0
    cand_emb = await embed_text(candidate_text)
    embedding_calls += 1

    escalation.sort(key=lambda pair: pair[1], reverse=True)

    for inc, _j in escalation:
        if inc.embedding is None:
            inc.embedding = await embed_text(inc.text)
            embedding_calls += 1
            session.add(
                ArticleEmbedding(
                    article_id=inc.article_id,
                    embedding=inc.embedding,
                    model=settings.openai_model_embedding,
                )
            )
        cos = _cosine(cand_emb, inc.embedding)
        if cos >= cosine_threshold:
            return DedupDecision(
                accept=False,
                reason="embedding",
                matched_article_id=inc.article_id,
                candidate_embedding=None,
                embedding_calls=embedding_calls,
            )

    return DedupDecision(
        accept=True,
        reason=None,
        matched_article_id=None,
        candidate_embedding=cand_emb,
        embedding_calls=embedding_calls,
    )
