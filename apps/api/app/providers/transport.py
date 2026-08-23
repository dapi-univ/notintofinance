import asyncio
import hashlib
import json
import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import perf_counter

import httpx

SENSITIVE_PARAMETER_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "key",
    "password",
    "secret",
    "token",
}


class ProviderBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderRequestEvent:
    provider: str
    dataset: str
    endpoint_name: str
    request_fingerprint: str
    requested_at: datetime
    completed_at: datetime
    status_code: int | None
    latency_ms: int
    attempt_number: int
    quota_limit: int | None
    quota_remaining_minute: int | None
    quota_remaining_month: int | None
    plan_expired: bool | None
    cache_status: str | None
    rows_received: int | None
    error_class: str | None
    warning: str | None


RequestEventSink = Callable[[ProviderRequestEvent], Awaitable[None]]


@dataclass
class RequestBudget:
    daily_soft_limit: int = 800
    monthly_reserve: int = 2500
    run_limit: int | None = None
    requests_today: int = 0
    requests_this_run: int = 0
    remaining_month: int | None = None

    def ensure_available(self, *, critical: bool) -> None:
        if self.run_limit is not None and self.requests_this_run >= self.run_limit:
            raise ProviderBudgetExceeded("provider run request cap reached")
        if not critical and self.requests_today >= self.daily_soft_limit:
            raise ProviderBudgetExceeded("provider daily soft budget reached")
        if (
            not critical
            and self.remaining_month is not None
            and self.remaining_month <= self.monthly_reserve
        ):
            raise ProviderBudgetExceeded("provider monthly quota reserve reached")

    def consume(self) -> None:
        self.requests_today += 1
        self.requests_this_run += 1


class QuotaAwareTransport:
    def __init__(
        self,
        *,
        provider: str,
        client: httpx.AsyncClient | None = None,
        concurrency: int = 2,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        budget: RequestBudget | None = None,
        event_sink: RequestEventSink | None = None,
        expect_quota_headers: bool = True,
    ) -> None:
        if concurrency < 1:
            raise ValueError("provider concurrency must be positive")
        self.provider = provider
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._budget = budget or RequestBudget()
        self._event_sink = event_sink
        self._expect_quota_headers = expect_quota_headers
        self._semaphore = asyncio.Semaphore(concurrency)

    @property
    def budget(self) -> RequestBudget:
        return self._budget

    async def get_json(
        self,
        *,
        dataset: str,
        endpoint_name: str,
        url: str,
        params: Mapping[str, str | int | bool],
        headers: Mapping[str, str],
        critical: bool = False,
    ) -> dict[str, object]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            async with self._semaphore:
                for attempt in range(1, self._max_retries + 2):
                    self._budget.ensure_available(critical=critical)
                    requested_at = datetime.now(UTC)
                    started = perf_counter()
                    response: httpx.Response | None = None
                    error: Exception | None = None
                    payload: dict[str, object] | None = None
                    try:
                        self._budget.consume()
                        response = await client.get(url, params=params, headers=headers)
                        if (
                            response.status_code == 429 or response.status_code >= 500
                        ) and attempt <= self._max_retries:
                            event = self._event(
                                dataset,
                                endpoint_name,
                                params,
                                requested_at,
                                started,
                                attempt,
                                response,
                                None,
                                None,
                            )
                            await self._record(event)
                            if event.quota_remaining_month is not None:
                                self._budget.remaining_month = event.quota_remaining_month
                            await asyncio.sleep(_retry_delay(response, attempt - 1))
                            continue
                        response.raise_for_status()
                        candidate = response.json()
                        if not isinstance(candidate, dict):
                            raise ValueError("provider returned a non-object response")
                        payload = candidate
                    except httpx.RequestError as exc:
                        error = exc
                        if attempt <= self._max_retries:
                            await self._record(
                                self._event(
                                    dataset,
                                    endpoint_name,
                                    params,
                                    requested_at,
                                    started,
                                    attempt,
                                    response,
                                    error,
                                    None,
                                )
                            )
                            await asyncio.sleep(_backoff_delay(attempt - 1))
                            continue
                    except Exception as exc:
                        error = exc

                    event = self._event(
                        dataset,
                        endpoint_name,
                        params,
                        requested_at,
                        started,
                        attempt,
                        response,
                        error,
                        payload,
                    )
                    await self._record(event)
                    if event.quota_remaining_month is not None:
                        self._budget.remaining_month = event.quota_remaining_month
                    if error:
                        raise error
                    if payload is None:
                        raise RuntimeError("provider request returned no payload")
                    return payload
            raise RuntimeError("provider request retry loop exhausted")
        finally:
            if owns_client:
                await client.aclose()

    def _event(
        self,
        dataset: str,
        endpoint_name: str,
        params: Mapping[str, str | int | bool],
        requested_at: datetime,
        started: float,
        attempt: int,
        response: httpx.Response | None,
        error: Exception | None,
        payload: dict[str, object] | None,
    ) -> ProviderRequestEvent:
        headers = response.headers if response is not None else httpx.Headers()
        quota_limit, limit_warning = _parse_int_header(headers, "x-ratelimit-limit")
        remaining_minute, minute_warning = _parse_int_header(
            headers, "x-ratelimit-remaining-minute"
        )
        remaining_month, month_warning = _parse_int_header(headers, "x-ratelimit-remaining-month")
        plan_expired, plan_warning = _parse_bool_header(headers, "x-plan-expired")
        warnings = [
            warning
            for warning in (limit_warning, minute_warning, month_warning, plan_warning)
            if warning
        ]
        if not self._expect_quota_headers:
            warnings = [warning for warning in warnings if "malformed" in warning]
        return ProviderRequestEvent(
            provider=self.provider,
            dataset=dataset,
            endpoint_name=endpoint_name,
            request_fingerprint=request_fingerprint(endpoint_name, params),
            requested_at=requested_at,
            completed_at=datetime.now(UTC),
            status_code=response.status_code if response is not None else None,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
            attempt_number=attempt,
            quota_limit=quota_limit,
            quota_remaining_minute=remaining_minute,
            quota_remaining_month=remaining_month,
            plan_expired=plan_expired,
            cache_status=headers.get("x-cache"),
            rows_received=_infer_rows(payload),
            error_class=type(error).__name__ if error else None,
            warning="; ".join(warnings) or None,
        )

    async def _record(self, event: ProviderRequestEvent) -> None:
        if self._event_sink:
            await self._event_sink(event)


def request_fingerprint(endpoint_name: str, params: Mapping[str, str | int | bool]) -> str:
    safe = {
        key: "[REDACTED]" if key.lower() in SENSITIVE_PARAMETER_NAMES else value
        for key, value in sorted(params.items())
    }
    material = json.dumps(
        {"endpoint": endpoint_name, "params": safe}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _parse_int_header(headers: httpx.Headers, name: str) -> tuple[int | None, str | None]:
    raw = headers.get(name)
    if raw is None:
        return None, f"missing {name}"
    try:
        value = int(raw)
    except ValueError:
        return None, f"malformed {name}"
    if value < 0:
        return None, f"malformed {name}"
    return value, None


def _parse_bool_header(headers: httpx.Headers, name: str) -> tuple[bool | None, str | None]:
    raw = headers.get(name)
    if raw is None:
        return None, f"missing {name}"
    normalized = raw.strip().lower()
    if normalized in {"true", "1"}:
        return True, None
    if normalized in {"false", "0"}:
        return False, None
    return None, f"malformed {name}"


def _infer_rows(payload: dict[str, object] | None) -> int | None:
    if payload is None:
        return None
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(body, dict):
        return None
    for key in ("items", "data", "rt", "brokerSummary", "bids", "asks"):
        candidate = body.get(key)
        if isinstance(candidate, list):
            return len(candidate)
    return None


def _backoff_delay(attempt: int) -> float:
    return 0.2 * (2**attempt) + random.uniform(0, 0.1)


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(float(retry_after), 0)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(retry_after)
                return max((parsed - datetime.now(UTC)).total_seconds(), 0)
            except (TypeError, ValueError):
                pass
    return _backoff_delay(attempt)
