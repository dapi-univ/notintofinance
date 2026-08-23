from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers.transport import (
    ProviderBudgetExceeded,
    QuotaAwareTransport,
    RequestBudget,
    request_fingerprint,
)


async def test_quota_headers_and_missing_header_warning_are_recorded() -> None:
    events = []

    async def sink(event: object) -> None:
        events.append(event)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={
                "X-RateLimit-Remaining-Minute": "1999",
                "X-RateLimit-Remaining-Month": "24452",
                "X-Cache": "MISS",
            },
            json={"data": {"items": [1, 2]}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = QuotaAwareTransport(
            provider="zapi", client=client, event_sink=sink  # type: ignore[arg-type]
        )
        await transport.get_json(
            dataset="stock-history",
            endpoint_name="stock-history",
            url="https://provider.invalid/stock-history",
            params={"code": "BBCA"},
            headers={"x-api-key": "fixture-secret"},
        )

    event = events[0]
    assert event.quota_remaining_minute == 1999
    assert event.quota_remaining_month == 24452
    assert event.rows_received == 2
    assert event.warning == "missing x-ratelimit-limit; missing x-plan-expired"
    assert "fixture-secret" not in event.request_fingerprint


async def test_monthly_reserve_and_daily_budget_stop_before_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=request, json={})

    budget = RequestBudget(daily_soft_limit=1, monthly_reserve=2500, remaining_month=2500)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = QuotaAwareTransport(provider="zapi", client=client, budget=budget)
        with pytest.raises(ProviderBudgetExceeded, match="monthly quota reserve"):
            await transport.get_json(
                dataset="history",
                endpoint_name="history",
                url="https://provider.invalid/history",
                params={},
                headers={},
            )
    assert calls == 0


async def test_429_honors_retry_after_exactly(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, request=request, headers={"Retry-After": "1.5"})
        return httpx.Response(200, request=request, json={})

    sleep = AsyncMock()
    monkeypatch.setattr("app.providers.transport.asyncio.sleep", sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = QuotaAwareTransport(provider="zapi", client=client, max_retries=1)
        await transport.get_json(
            dataset="history",
            endpoint_name="history",
            url="https://provider.invalid/history",
            params={},
            headers={},
        )

    assert calls == 2
    sleep.assert_awaited_once_with(1.5)


async def test_retry_response_updates_observed_monthly_quota() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                request=request,
                headers={
                    "Retry-After": "0",
                    "X-RateLimit-Remaining-Month": "2499",
                },
            )
        return httpx.Response(200, request=request, json={})

    budget = RequestBudget(monthly_reserve=2500)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = QuotaAwareTransport(
            provider="zapi", client=client, max_retries=1, budget=budget
        )
        with pytest.raises(ProviderBudgetExceeded, match="monthly quota reserve"):
            await transport.get_json(
                dataset="history",
                endpoint_name="history",
                url="https://provider.invalid/history",
                params={},
                headers={},
            )

    assert calls == 1


async def test_ordinary_4xx_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = QuotaAwareTransport(provider="zapi", client=client, max_retries=3)
        with pytest.raises(httpx.HTTPStatusError):
            await transport.get_json(
                dataset="history",
                endpoint_name="history",
                url="https://provider.invalid/history",
                params={},
                headers={},
            )
    assert calls == 1


def test_request_fingerprint_redacts_sensitive_parameters() -> None:
    first = request_fingerprint("endpoint", {"code": "BBCA", "token": "first"})
    second = request_fingerprint("endpoint", {"code": "BBCA", "token": "second"})
    assert first == second
