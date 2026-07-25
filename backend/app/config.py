from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://tasbir:tasbir@localhost:5432/tasbir"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "tasbir"
    minio_secret_key: str = "tasbir_secret"
    minio_bucket: str = "tasbir-assets"

    # Ghost CMS
    ghost_url: str = ""
    ghost_admin_api_key: str = ""
    ghost_webhook_secret: str = ""

    # Penpot
    penpot_url: str = "http://localhost:9002"
    penpot_access_token: str = ""

    # Unsplash
    unsplash_access_key: str = ""

    # API
    api_keys: str = ""
    cors_origins: list[str] = ["*"]
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60

    # Logging
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
