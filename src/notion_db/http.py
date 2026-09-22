"""notion-db's own async HTTP client for the Notion API.

Replaces notion_client.AsyncClient: a small transport built directly on
httpx, specialized to what notion-db needs (databases/data_sources/pages
endpoints only), with built-in retry/backoff on 429/5xx, a client-side
token-bucket rate limiter tuned to Notion's ~3 req/sec integration limit,
and structured logging that never leaks the auth token.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_INITIAL_RETRY_DELAY_S = 1.0
DEFAULT_MAX_RETRY_DELAY_S = 60.0
RATE_LIMIT_RPS = 3.0
RATE_LIMIT_BURST = 3.0

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

logger = logging.getLogger("notion_db.http")


class NotionHTTPError(Exception):
    """Raised for any non-2xx response from the Notion API.

    Carries the same attribute surface notion_client's APIResponseError did
    (code/status/headers/body/request_id) so exceptions.translate_error()
    keeps working unchanged via duck-typing on `.code`.
    """

    def __init__(
        self,
        *,
        code: str,
        status: int,
        message: str,
        headers: httpx.Headers,
        raw_body_text: str,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.headers = headers
        self.body = raw_body_text
        self.request_id = request_id


def _build_http_error(response: httpx.Response) -> NotionHTTPError:
    raw_body_text = response.text
    try:
        body = response.json()
    except ValueError:
        body = {}
    code = body.get("code") or "notion_db_unknown_error"
    message = body.get("message") or raw_body_text or f"HTTP {response.status_code}"
    return NotionHTTPError(
        code=code,
        status=response.status_code,
        message=message,
        headers=response.headers,
        raw_body_text=raw_body_text,
        request_id=response.headers.get("x-request-id"),
    )


class TokenBucket:
    """An async token-bucket limiter: `rate` tokens/sec, capacity `capacity`.

    One instance is owned per NotionTransport (i.e. per AsyncNotionDB
    instance by default). Multiple instances sharing the same token each get
    their own independent budget, so in aggregate they could exceed Notion's
    per-integration limit -- an accepted v1 simplification.
    """

    def __init__(
        self, rate: float = RATE_LIMIT_RPS, capacity: float = RATE_LIMIT_BURST
    ) -> None:
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._updated_at
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._updated_at = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await asyncio.sleep((1 - self._tokens) / self._rate)


def _compute_backoff(attempt: int, retry_after: float | None) -> float:
    if retry_after is not None:
        return min(retry_after, DEFAULT_MAX_RETRY_DELAY_S)
    base = DEFAULT_INITIAL_RETRY_DELAY_S * (2**attempt)
    jitter = random.uniform(0, base * 0.25)
    return min(base + jitter, DEFAULT_MAX_RETRY_DELAY_S)


def _redact_headers(headers: httpx.Headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() != "authorization"}


class NotionTransport:
    """Low-level async HTTP transport for the Notion API."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate_limiter: TokenBucket | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
        )
        self._max_retries = max_retries
        self._rate_limiter = rate_limiter or TokenBucket()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempt = 0
        while True:
            await self._rate_limiter.acquire()
            start = time.monotonic()
            response = await self._client.request(
                method, path, params=params, json=json_body
            )
            elapsed = time.monotonic() - start
            logger.info(
                "%s %s -> %s in %.3fs (attempt=%d)",
                method,
                path,
                response.status_code,
                elapsed,
                attempt,
            )
            logger.debug(
                "request headers=%s body=%s | response headers=%s body=%s",
                _redact_headers(response.request.headers),
                json_body,
                dict(response.headers),
                response.text,
            )

            if response.status_code < 300:
                return response.json() if response.content else {}

            if (
                response.status_code in _RETRYABLE_STATUSES
                and attempt < self._max_retries
            ):
                retry_after_header = response.headers.get("retry-after")
                retry_after = float(retry_after_header) if retry_after_header else None
                delay = _compute_backoff(attempt, retry_after)
                await asyncio.sleep(delay)
                attempt += 1
                continue

            raise _build_http_error(response)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def _strip_none(values: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in values.items() if v is not None}


class _DatabasesNamespace:
    def __init__(self, transport: NotionTransport) -> None:
        self._t = transport

    async def retrieve(self, *, database_id: str) -> dict[str, Any]:
        return await self._t.request("GET", f"/databases/{database_id}")


class _DataSourcesNamespace:
    def __init__(self, transport: NotionTransport) -> None:
        self._t = transport

    async def retrieve(self, *, data_source_id: str) -> dict[str, Any]:
        return await self._t.request("GET", f"/data_sources/{data_source_id}")

    async def query(
        self,
        *,
        data_source_id: str,
        page_size: int = 100,
        filter: dict[str, Any] | None = None,
        sorts: list[Any] | None = None,
        start_cursor: str | None = None,
    ) -> dict[str, Any]:
        body = _strip_none(
            {
                "page_size": page_size,
                "filter": filter,
                "sorts": sorts,
                "start_cursor": start_cursor,
            }
        )
        return await self._t.request(
            "POST", f"/data_sources/{data_source_id}/query", json_body=body
        )


class _PagesNamespace:
    def __init__(self, transport: NotionTransport) -> None:
        self._t = transport

    async def create(
        self, *, parent: dict[str, Any], properties: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._t.request(
            "POST", "/pages", json_body={"parent": parent, "properties": properties}
        )

    async def retrieve(self, *, page_id: str) -> dict[str, Any]:
        return await self._t.request("GET", f"/pages/{page_id}")

    async def update(
        self,
        *,
        page_id: str,
        properties: dict[str, Any] | None = None,
        archived: bool | None = None,
    ) -> dict[str, Any]:
        body = _strip_none({"properties": properties, "archived": archived})
        return await self._t.request("PATCH", f"/pages/{page_id}", json_body=body)


class NotionAPIClient:
    """Drop-in replacement for notion_client.AsyncClient, specialized to what notion-db needs."""

    def __init__(self, token: str, **transport_kwargs: Any) -> None:
        self._transport = NotionTransport(token, **transport_kwargs)
        self.databases = _DatabasesNamespace(self._transport)
        self.data_sources = _DataSourcesNamespace(self._transport)
        self.pages = _PagesNamespace(self._transport)

    async def aclose(self) -> None:
        await self._transport.aclose()
