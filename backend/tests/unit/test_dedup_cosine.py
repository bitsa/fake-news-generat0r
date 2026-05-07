from app.services.dedup import _cosine


def test_cosine_returns_one_for_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert _cosine(v, v) == 1.0


def test_cosine_returns_zero_for_orthogonal_vectors():
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_returns_zero_when_either_vector_is_zero_norm():
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert _cosine([1.0, 1.0], [0.0, 0.0]) == 0.0
