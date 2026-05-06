from enum import StrEnum


class Source(StrEnum):
    NYT = "NYT"
    NPR = "NPR"
    GUARDIAN = "Guardian"


FEED_URLS: dict[Source, str] = {
    Source.NYT: "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    Source.NPR: "https://feeds.npr.org/1001/rss.xml",
    Source.GUARDIAN: "https://www.theguardian.com/world/rss",
}
