import pytest

from app.services.dedup import _cosine


def test_cosine_returns_one_for_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert _cosine(v, v) == pytest.approx(1.0, abs=1e-12)


def test_cosine_returns_zero_for_orthogonal_vectors():
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0, abs=1e-12)


def test_cosine_returns_zero_when_either_vector_is_zero_norm():
    assert _cosine([0.0, 0.0], [1.0, 1.0]) == pytest.approx(0.0, abs=1e-12)
    assert _cosine([1.0, 1.0], [0.0, 0.0]) == pytest.approx(0.0, abs=1e-12)
