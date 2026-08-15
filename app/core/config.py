"""Centralized application settings."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_name: str = "AI Resume Matcher"
    app_version: str = "0.1.0"
    app_env: str = "development"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"


settings = Settings()
