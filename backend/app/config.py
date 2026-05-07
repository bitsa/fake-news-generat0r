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
    scrape_interval_minutes: int = 60
    transform_recovery_threshold_minutes: int = Field(default=5, gt=0)


settings = Settings()
