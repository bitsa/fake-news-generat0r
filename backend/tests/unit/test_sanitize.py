import inspect

from app.services import sanitize
from app.services.sanitize import clean_text


def test_clean_text_decodes_named_entity_amp():
    assert clean_text("Apples &amp; oranges") == "Apples & oranges"


def test_clean_text_decodes_numeric_entity_apostrophe():
    assert clean_text("it&#39;s") == "it's"


def test_clean_text_decodes_named_entity_nbsp():
    result = clean_text("a&nbsp;b")
    assert "&nbsp;" not in result
    assert result == "a b"


def test_clean_text_strips_paragraph_tag():
    assert clean_text("<p>hi</p>") == "hi"


def test_clean_text_strips_anchor_tag_with_attributes():
    assert clean_text('<a href="http://x">link</a>') == "link"


def test_clean_text_strips_self_closing_img_tag():
    assert clean_text('<img src="x"/>hi') == "hi"


def test_clean_text_strips_self_closing_br_tag():
    result = clean_text("a<br/>b")
    assert "a" in result
    assert "b" in result
    assert result == "a b"


def test_clean_text_does_not_fuse_words_across_tags():
    result = clean_text("<p>Hello</p><p>world</p>")
    assert "Hello" in result
    assert "world" in result
    assert "Helloworld" not in result


def test_clean_text_collapses_mixed_whitespace_runs():
    assert clean_text("a \t\n  b") == "a b"


def test_clean_text_strips_leading_and_trailing_whitespace():
    assert clean_text("   hello   ") == "hello"


def test_clean_text_returns_empty_string_for_tag_only_input():
    assert clean_text("<p></p>") == ""


def test_clean_text_returns_empty_string_for_entity_and_whitespace_only_input():
    assert clean_text("&nbsp; \n") == ""


def test_clean_text_is_idempotent():
    for s in ("hello", "a b c", "it's & more"):
        once = clean_text(s)
        assert once == s
        assert clean_text(once) == once


def test_clean_text_module_imports_only_stdlib():
    source = inspect.getsource(sanitize)
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert import_lines == ["import html", "import re"]
