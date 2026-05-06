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
    prompt_version_transform: str = "v1"
    rss_feeds: str = ""
    scrape_interval_minutes: int = 60
    llm_cache_ttl_seconds: int = 3600


settings = Settings()
