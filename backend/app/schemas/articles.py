from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    title: str
    description: str | None
    url: str
    published_at: datetime | None
    created_at: datetime


class FakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(validation_alias="article_id")
    title: str | None
    description: str | None
    model: str | None
    temperature: float | None
    created_at: datetime


class ArticlePairOut(BaseModel):
    id: int
    article: ArticleOut
    fake: FakeOut


class ArticlesResponse(BaseModel):
    total: int
    pending: int
    articles: list[ArticlePairOut]
