from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        default="sqlite:///./eternalgy.db",
        description="SQLAlchemy database URL. Defaults to local SQLite for development.",
    )
    backend_api_key: str = Field(default="dev-secret-key")
    log_level: str = Field(default="info")
    timezone: str = Field(default="Asia/Kuala_Lumpur")
    sse_heartbeat_seconds: int = Field(default=15, ge=5)

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=".env",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
