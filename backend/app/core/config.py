from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Values are read from environment variables / `.env`. When running via
    docker-compose, service env vars (e.g. POSTGRES_HOST=db) take precedence
    over whatever is in `.env`, so the same image works both containerized
    and against a locally installed Postgres/Redis.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "FastAPI Template"
    ENV: Literal["local", "test", "staging", "production"] = "local"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    CACHE_DEFAULT_TTL_SECONDS: int = 300

    BACKEND_CORS_ORIGINS: list[str] = []

    # Base URL of the web app — links in emails point there.
    FRONTEND_URL: str = "http://localhost:5173"

    # Any SMTP provider; defaults match the Mailpit container from docker-compose.
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = False
    EMAIL_FROM: str = "Self Forge <noreply@selfforge.local>"

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802 (kept uppercase to match the settings fields)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:  # noqa: N802
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def is_local(self) -> bool:
        return self.ENV == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
