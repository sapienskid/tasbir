from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    # LLM
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    # Preferred generation transport: "direct" (ChatGoogleGenerativeAI) or
    # "gateway" (Cloudflare AI Gateway unified REST). Gateway keeps working
    # when keys rotate; direct stays as the emergency fallback.
    llm_provider: str = "direct"

    # Cloudflare AI Gateway (single AI control plane for generation +
    # decisions). Jev + Clef both run through here — no TypeSafe key needed
    # (Jev bills as a third-party model via Unified Billing).
    # Canonical env names (as in .env): CLOUDFLARE_ACCOUNT_ID and
    # CLOUDFLARE_AI_GATEWAY_TOKEN. CF_ACCOUNT_ID / CF_AIG_TOKEN stay as
    # legacy aliases.
    cloudflare_account_id: str = ""
    cloudflare_ai_gateway_token: str = ""
    cf_account_id: str = ""
    cf_aig_token: str = ""
    cf_gateway_id: str = "tasbir"
    # Decision-model routing order, e.g. "jev,clef-flash,clef".
    decision_provider_order: str = "jev,clef-flash,clef"
    # Dual-run calibration: fraction sampled + log disagreements (0 disables).
    decision_calibration_rate: float = 0.0
    # Copy QA starts advisory-only in the Studio; blocking enforced per setting.
    copy_qa_enforce: bool = False

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
    # Separate bucket for interactive editor traffic (previews, refill,
    # editor state, compose previews/thumbnails) so editing never starves
    # or gets starved by generation calls. <= 0 disables the tier.
    rate_limit_interactive_per_min: int = 600

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

    @property
    def resolved_cf_account_id(self) -> str:
        """Account id from either naming (canonical name wins)."""
        return self.cloudflare_account_id or self.cf_account_id

    @property
    def resolved_cf_token(self) -> str:
        """Gateway token from either naming (canonical name wins)."""
        return self.cloudflare_ai_gateway_token or self.cf_aig_token

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
