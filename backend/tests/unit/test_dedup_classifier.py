from unittest.mock import MagicMock

import pytest

from app.config import settings
from app.models import ArticleEmbedding
from app.services.dedup import Incumbent, find_near_duplicate, tokenize


@pytest.fixture(autouse=True)
def _force_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "openai_mock_mode", True)
    monkeypatch.setattr(settings, "dedup_jaccard_high", 0.80)
    monkeypatch.setattr(settings, "dedup_jaccard_floor", 0.40)
    monkeypatch.setattr(settings, "dedup_cosine_threshold", 0.88)
    monkeypatch.setattr(settings, "openai_model_embedding", "text-embedding-3-small")


def _session() -> MagicMock:
    s = MagicMock()
    s.add = MagicMock()
    return s


def _inc(article_id: int, title: str, embedding=None) -> Incumbent:
    return Incumbent(
        article_id=article_id,
        tokens=tokenize(title),
        text=f"{title}\n\nbody for {article_id}",
        embedding=embedding,
    )


async def test_high_band_jaccard_skip_returns_reason_jaccard_no_embedding_call():
    session = _session()
    incumbents = [_inc(7, "Mayor announces budget cuts for next fiscal year")]
    decision = await find_near_duplicate(
        session,
        candidate_title="Mayor announces budget cuts for next fiscal year",
        candidate_text="title\n\nbody",
        incumbents=incumbents,
    )
    assert decision.accept is False
    assert decision.reason == "jaccard"
    assert decision.embedding_calls == 0


async def test_high_band_skip_carries_matched_article_id_of_argmax_incumbent():
    session = _session()
    incumbents = [
        _inc(1, "completely unrelated headline trees forest"),
        _inc(99, "Mayor announces budget cuts for next fiscal year"),
    ]
    decision = await find_near_duplicate(
        session,
        candidate_title="Mayor announces budget cuts for next fiscal year",
        candidate_text="t\n\nb",
        incumbents=incumbents,
    )
    assert decision.matched_article_id == 99


async def test_low_band_insert_returns_accept_no_embedding_no_call():
    session = _session()
    incumbents = [_inc(1, "completely different topic about kittens")]
    decision = await find_near_duplicate(
        session,
        candidate_title="financial markets close higher today",
        candidate_text="t\n\nb",
        incumbents=incumbents,
    )
    assert decision.accept is True
    assert decision.reason is None
    assert decision.candidate_embedding is None
    assert decision.embedding_calls == 0


async def test_ambiguous_band_with_cosine_match_returns_reason_embedding(monkeypatch):
    session = _session()
    # candidate vs incumbent: jaccard ~ 0.5 (ambiguous band).
    incumbents = [
        _inc(
            42,
            "election results count voter turnout high",
            embedding=[1.0] * 1536,
        ),
    ]
    captured: list[str] = []

    async def fake_embed(text: str) -> list[float]:
        captured.append(text)
        return [1.0] * 1536  # cosine == 1.0 with incumbent → match

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)

    decision = await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout final",
        candidate_text="cand text",
        incumbents=incumbents,
    )
    assert decision.accept is False
    assert decision.reason == "embedding"
    assert decision.matched_article_id == 42
    assert decision.embedding_calls == 1  # only candidate embedded; incumbent warm


async def test_ambiguous_band_no_match_returns_accept_with_candidate_embedding_persisted(  # noqa: E501
    monkeypatch,
):
    session = _session()
    incumbents = [
        _inc(
            42,
            "election results count voter turnout high",
            embedding=[1.0] + [0.0] * 1535,
        ),
    ]

    async def fake_embed(text: str) -> list[float]:
        # orthogonal to incumbent embedding → cosine 0
        return [0.0, 1.0] + [0.0] * 1534

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)

    decision = await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout final",
        candidate_text="cand text",
        incumbents=incumbents,
    )
    assert decision.accept is True
    assert decision.reason is None
    assert decision.candidate_embedding is not None
    assert len(decision.candidate_embedding) == 1536
    assert decision.embedding_calls == 1


async def test_ambiguous_band_only_escalates_against_incumbents_with_jaccard_above_floor(  # noqa: E501
    monkeypatch,
):
    session = _session()
    # one ambiguous-band incumbent, one low-band incumbent (should NOT be embedded)
    ambiguous = _inc(1, "election results count voter turnout high")
    low_band = _inc(2, "completely unrelated kittens puppies cats dogs")
    incumbents = [ambiguous, low_band]

    embed_calls: list[str] = []

    async def fake_embed(text: str) -> list[float]:
        embed_calls.append(text)
        return [0.0] * 1535 + [1.0]  # orthogonal to anything we'll set

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)

    await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout final",
        candidate_text="cand",
        incumbents=incumbents,
    )
    # candidate (1) + cold ambiguous incumbent (1) = 2.
    # low-band incumbent must NOT be embedded.
    assert len(embed_calls) == 2


async def test_jaccard_equal_to_high_threshold_is_skip(monkeypatch):
    session = _session()
    # Force exact jaccard == 0.80 by stubbing the function.
    inc = _inc(5, "doesnt matter")
    incumbents = [inc]
    monkeypatch.setattr(
        "app.services.dedup._jaccard", lambda a, b: 0.80 if b is inc.tokens else 0.0
    )
    decision = await find_near_duplicate(
        session,
        candidate_title="some candidate title",
        candidate_text="t",
        incumbents=incumbents,
    )
    assert decision.accept is False
    assert decision.reason == "jaccard"


async def test_jaccard_equal_to_floor_threshold_escalates_to_cosine(monkeypatch):
    session = _session()
    inc = _inc(5, "doesnt matter", embedding=[1.0] * 1536)
    incumbents = [inc]
    monkeypatch.setattr(
        "app.services.dedup._jaccard", lambda a, b: 0.40 if b is inc.tokens else 0.0
    )

    embed_calls = 0

    async def fake_embed(text: str) -> list[float]:
        nonlocal embed_calls
        embed_calls += 1
        return [0.0] * 1536  # cosine 0 → no match → insert

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)

    decision = await find_near_duplicate(
        session,
        candidate_title="some candidate title",
        candidate_text="t",
        incumbents=incumbents,
    )
    assert decision.accept is True
    assert embed_calls == 1


async def test_cosine_equal_to_threshold_is_skip(monkeypatch):
    session = _session()
    inc = _inc(5, "election results count voter turnout high", embedding=[1.0] * 1536)
    incumbents = [inc]

    async def fake_embed(text: str) -> list[float]:
        return [1.0] * 1536  # cosine == 1.0 ≥ 0.88

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)
    monkeypatch.setattr(settings, "dedup_cosine_threshold", 1.0)

    decision = await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout final",
        candidate_text="t",
        incumbents=incumbents,
    )
    assert decision.accept is False
    assert decision.reason == "embedding"


async def test_cold_incumbent_embedding_is_computed_and_persisted_on_first_use(
    monkeypatch,
):
    session = _session()
    inc = _inc(77, "election results count voter turnout high", embedding=None)
    incumbents = [inc]

    async def fake_embed(text: str) -> list[float]:
        return [0.0, 1.0] + [0.0] * 1534

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)

    decision = await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout final",
        candidate_text="cand",
        incumbents=incumbents,
    )

    # candidate + cold incumbent = 2 embedding calls.
    assert decision.embedding_calls == 2
    # session.add called with an ArticleEmbedding for incumbent 77.
    args = [c.args[0] for c in session.add.call_args_list]
    embeddings = [a for a in args if isinstance(a, ArticleEmbedding)]
    assert len(embeddings) == 1
    assert embeddings[0].article_id == 77


async def test_warm_incumbent_embedding_is_reused_no_extra_call(monkeypatch):
    session = _session()
    inc = _inc(77, "election results count voter turnout high", embedding=[0.0] * 1536)
    incumbents = [inc]

    embed_calls = 0

    async def fake_embed(text: str) -> list[float]:
        nonlocal embed_calls
        embed_calls += 1
        return [1.0] + [0.0] * 1535

    monkeypatch.setattr("app.services.dedup.embed_text", fake_embed)

    # First candidate run.
    await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout final",
        candidate_text="cand1",
        incumbents=incumbents,
    )
    first = embed_calls
    # Second candidate run; incumbent embedding should still be warm.
    await find_near_duplicate(
        session,
        candidate_title="election results count voter turnout decisive",
        candidate_text="cand2",
        incumbents=incumbents,
    )
    second = embed_calls - first
    assert first == 1  # candidate only
    assert second == 1  # candidate only — warm incumbent reused
    # Note: the incumbent had a pre-existing non-None embedding so it counts as
    # warm from the start; nothing was persisted to the session.
    added_embeddings = [
        c.args[0]
        for c in session.add.call_args_list
        if isinstance(c.args[0], ArticleEmbedding)
    ]
    assert added_embeddings == []
