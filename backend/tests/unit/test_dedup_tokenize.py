import pytest

from app.services.dedup import STOPWORDS, tokenize


def test_tokenize_lowercases_input():
    assert tokenize("HELLO WORLD") == {"hello", "world"}


def test_tokenize_strips_punctuation():
    assert tokenize("Apples, oranges! And; bananas?") == {
        "apples",
        "oranges",
        "bananas",
    }


def test_tokenize_splits_on_whitespace():
    assert tokenize("hello\tworld\nfoo bar") == {"hello", "world", "foo", "bar"}


def test_tokenize_drops_tokens_of_length_two_or_less():
    assert tokenize("ab abc abcd") == {"abc", "abcd"}


@pytest.mark.parametrize(
    "stopword",
    ["the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "at", "is"],
)
def test_tokenize_drops_each_of_the_twelve_stopwords(stopword):
    assert stopword not in tokenize(f"hello {stopword} world bigword")


def test_tokenize_stopword_set_size_is_exactly_twelve():
    assert len(STOPWORDS) == 12
    assert STOPWORDS == frozenset(
        {"the", "a", "an", "of", "to", "for", "and", "or", "in", "on", "at", "is"}
    )


def test_tokenize_does_not_consume_description():
    # Title-only coverage: tokenize takes a single string argument; the
    # signature itself proves description is not part of Jaccard input.
    import inspect

    sig = inspect.signature(tokenize)
    params = list(sig.parameters)
    assert params == ["title"]
