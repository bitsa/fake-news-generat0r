from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    is_error: bool
    request_id: str | None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    article_id: int
    messages: list[ChatMessageOut]
