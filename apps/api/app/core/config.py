from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str | None = None
    market_data_provider: str = "zapi"
    zapi_api_key: str | None = None
    zapi_base_url: str = "https://api.zpi.web.id/v1/finance:idx"
    zapi_pluang_base_url: str = "https://api.zpi.web.id/v1/finance:pluang"
    provider_concurrency: int = Field(default=2, ge=1, le=10)
    provider_timeout_seconds: float = Field(default=30, gt=0, le=120)
    provider_daily_soft_budget: int = Field(default=800, ge=1)
    provider_monthly_reserve: int = Field(default=2500, ge=0)
    provider_canary_request_cap: int = Field(default=30, ge=1, le=100)
    raw_payload_retention_days: int = Field(default=7, ge=1, le=90)
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")

    @property
    def effective_provider(self) -> str:
        return self.market_data_provider.strip().lower()

    @property
    def normalized_app_env(self) -> str:
        return self.app_env.strip().lower()

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
