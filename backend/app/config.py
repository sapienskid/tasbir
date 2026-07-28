from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Database (SQLite)
    database_url: str = "sqlite+aiosqlite:///data/tasbir.db"

    # Redis (Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_keys: str = ""
    cors_origins: list[str] = ["*"]

    # Logging
    log_level: str = "info"

    # Output
    output_dir: str = "data/output"
    tokens_path: str = "data/design_system/tokens.yaml"
    brand_path: str = "data/design_system/brand.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
