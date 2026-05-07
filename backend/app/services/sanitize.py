import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_text(s: str) -> str:
    s = html.unescape(s)
    s = _TAG_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()
