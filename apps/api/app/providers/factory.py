from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.mock import MockMarketDataProvider
from app.providers.zapi import ZapiProvider


def create_provider(settings: Settings) -> MarketDataProvider:
    if settings.effective_provider == "mock":
        return MockMarketDataProvider()
    if settings.effective_provider == "zapi" and settings.zapi_api_key:
        return ZapiProvider(settings.zapi_api_key, settings.zapi_base_url)
    raise ValueError(f"unsupported market data provider: {settings.effective_provider}")
