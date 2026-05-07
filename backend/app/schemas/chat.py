from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from app.config import settings


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


class ChatPostRequest(BaseModel):
    message: StrictStr

    @field_validator("message")
    @classmethod
    def _validate_message(cls, v: str) -> str:
        if v == "" or v.strip() == "":
            raise ValueError("message must not be empty or whitespace-only")
        if len(v) > settings.chat_message_max_chars:
            raise ValueError(
                f"message exceeds maximum length of "
                f"{settings.chat_message_max_chars} characters"
            )
        return v
