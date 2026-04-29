from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/pitchmind"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/pitchmind_test"
    REDIS_URL: str = "redis://localhost:6379"

    ANTHROPIC_API_KEY: str = "sk-ant-placeholder"
    GEMINI_API_KEY: str = ""
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GCS_PROJECT_ID: str = ""
    GCS_BUCKET: str = "pitchmind-files"
    GCS_CREDENTIALS_JSON: str = ""

    FRONTEND_URL: str = "http://localhost:5173"
    ENVIRONMENT: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
