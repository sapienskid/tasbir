from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    # LLM
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Stock-photo providers (media tools). Wikimedia Commons needs no key.
    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    # Database (SQLite)
    database_url: str = "sqlite+aiosqlite:///data/tasbir.db"

    # Redis (Celery broker)
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_keys: str = ""
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173", "http://localhost:3000"
    ]
    rate_limit_per_min: int = 30

    # Playwright render service
    render_service_key: str = ""
    renderer_url: str = "http://playwright:4000"

    # Image loading / SSRF guard
    image_allow_hosts: str = ""
    image_max_bytes: int = 10 * 1024 * 1024
    image_max_redirects: int = 2

    # Retention
    output_ttl_hours: int = 24

    # If true, a downloaded artifact is deleted after delivery (old one-time
    # behavior). Default keeps files until the TTL sweep; per-request
    # ?consume=true overrides.
    delete_on_download: bool = False

    # Verification
    skip_verify: bool = False

    # Logging
    log_level: str = "info"

    # Design system paths
    output_dir: str = "data/output"
    design_system_dir: str = "data/design_system"
    tokens_path: str = "data/design_system/tokens.yaml"
    brand_path: str = "data/design_system/brand.yaml"
    platforms_path: str = "data/design_system/platforms.yaml"
    campaigns_path: str = "data/design_system/campaigns.yaml"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        """Accept both JSON arrays and comma-separated origin strings."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
