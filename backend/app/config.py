from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    redis_url: str
    openai_api_key: str = Field(repr=False)
    openai_model_transform: str = "gpt-4o-mini"
    openai_model_chat: str = "gpt-4o-mini"
    openai_temperature_transform: float = 0.9
    openai_temperature_chat: float = 0.7
    openai_request_timeout_seconds: int = Field(default=30, gt=0)
    openai_mock_mode: bool = False
    scrape_max_per_source: int = 10
    transform_recovery_threshold_minutes: int = Field(default=5, gt=0)
    chat_message_max_chars: int = Field(default=512, gt=0)
    chat_mock_force_error_token: str | None = None
    chat_llm_mock: bool = True
    chat_history_window: int = Field(default=10, gt=0)
    chat_max_output_tokens: int = Field(default=512, gt=0)
    dedup_window_hours: int = Field(default=168, gt=0)
    dedup_jaccard_high: float = Field(default=0.80, gt=0.0, le=1.0)
    dedup_jaccard_floor: float = Field(default=0.40, ge=0.0, le=1.0)
    dedup_cosine_threshold: float = Field(default=0.88, gt=0.0, le=1.0)
    openai_model_embedding: str = "text-embedding-3-small"


settings = Settings()
