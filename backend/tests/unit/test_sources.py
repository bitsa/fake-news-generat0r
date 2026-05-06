from app.sources import FEED_URLS, Source


def test_source_members_exact():
    assert set(Source) == {Source.NYT, Source.NPR, Source.GUARDIAN}
    assert len(Source) == 3


def test_source_member_values():
    assert Source.NYT.value == "NYT"
    assert Source.NPR.value == "NPR"
    assert Source.GUARDIAN.value == "Guardian"


def test_source_is_strenum():
    assert issubclass(Source, str)
    assert Source.NYT == "NYT"
    assert Source.NPR == "NPR"
    assert Source.GUARDIAN == "Guardian"


def test_source_declaration_order():
    assert list(Source) == [Source.NYT, Source.NPR, Source.GUARDIAN]


def test_feed_urls_keys_match_source():
    assert set(FEED_URLS) == set(Source)


def test_feed_urls_has_exactly_three_entries():
    assert len(FEED_URLS) == 3


def test_feed_urls_values_exact():
    assert (
        FEED_URLS[Source.NYT]
        == "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
    )
    assert FEED_URLS[Source.NPR] == "https://feeds.npr.org/1001/rss.xml"
    assert FEED_URLS[Source.GUARDIAN] == "https://www.theguardian.com/world/rss"
    for url in FEED_URLS.values():
        assert url.startswith("https://")
