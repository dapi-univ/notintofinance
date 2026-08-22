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
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")

    @property
    def effective_provider(self) -> str:
        if self.market_data_provider == "zapi" and not self.zapi_api_key:
            return "mock"
        return self.market_data_provider

    @property
    def parsed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
