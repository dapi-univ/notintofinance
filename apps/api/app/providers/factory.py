from app.core.config import Settings
from app.providers.base import MarketDataProvider
from app.providers.mock import MockMarketDataProvider
from app.providers.transport import QuotaAwareTransport
from app.providers.zapi import RawPayloadSink, ZapiProvider


def create_provider(
    settings: Settings,
    *,
    transport: QuotaAwareTransport | None = None,
    raw_payload_sink: RawPayloadSink | None = None,
) -> MarketDataProvider:
    if settings.effective_provider == "mock":
        if settings.normalized_app_env not in {"development", "test"}:
            raise ValueError("mock market data is only allowed in development or test")
        return MockMarketDataProvider()
    if settings.effective_provider == "zapi":
        if not settings.zapi_api_key:
            raise ValueError("ZAPI_API_KEY is required when MARKET_DATA_PROVIDER=zapi")
        return ZapiProvider(
            settings.zapi_api_key,
            settings.zapi_base_url,
            transport=transport,
            raw_payload_sink=raw_payload_sink,
        )
    raise ValueError(f"unsupported market data provider: {settings.effective_provider}")
