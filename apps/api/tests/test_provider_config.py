import pytest

from app.core.config import Settings
from app.providers.factory import create_provider
from app.providers.mock import MockMarketDataProvider


@pytest.mark.parametrize("app_env", ["production", "staging"])
def test_deployed_zapi_config_refuses_missing_credentials(app_env: str) -> None:
    settings = Settings(
        app_env=app_env,
        market_data_provider="zapi",
        zapi_api_key=None,
    )

    with pytest.raises(ValueError, match="ZAPI_API_KEY is required"):
        create_provider(settings)


def test_development_requires_explicit_mock_mode() -> None:
    settings = Settings(
        app_env="development",
        market_data_provider="mock",
        zapi_api_key=None,
    )

    assert isinstance(create_provider(settings), MockMarketDataProvider)


def test_deployed_environments_refuse_mock_provider() -> None:
    settings = Settings(app_env="production", market_data_provider="mock")

    with pytest.raises(ValueError, match="only allowed in development or test"):
        create_provider(settings)
