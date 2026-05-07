from app.services.dedup import _jaccard


def test_jaccard_returns_zero_for_disjoint_sets():
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_returns_one_for_identical_sets():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_returns_zero_when_both_sets_empty():
    assert _jaccard(set(), set()) == 0.0
