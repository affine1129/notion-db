from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from notion_db.http import NotionHTTPError, NotionTransport, TokenBucket


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://api.notion.com/v1",
        transport=httpx.MockTransport(handler),
        headers={
            "Authorization": "Bearer secret-token-xyz",
            "Notion-Version": "2025-09-03",
            "Content-Type": "application/json",
        },
    )


@pytest.mark.asyncio
async def test_successful_request_returns_parsed_json_and_sends_auth_headers():
    seen_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, json={"id": "abc123"})

    http_client = _client_with_handler(handler)
    transport = NotionTransport("secret-token-xyz", http_client=http_client)

    result = await transport.request("GET", "/pages/abc123")

    assert result == {"id": "abc123"}
    assert len(seen_requests) == 1
    assert seen_requests[0].headers["authorization"] == "Bearer secret-token-xyz"
    assert seen_requests[0].headers["notion-version"] == "2025-09-03"


@pytest.mark.asyncio
async def test_429_with_retry_after_retries_and_succeeds():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                429, headers={"Retry-After": "2"}, json={"code": "rate_limited"}
            )
        return httpx.Response(200, json={"ok": True})

    http_client = _client_with_handler(handler)
    transport = NotionTransport("secret-token-xyz", http_client=http_client)

    with patch("notion_db.http.asyncio.sleep", new=AsyncMock()) as mock_sleep:
        result = await transport.request("GET", "/pages/p1")

    assert result == {"ok": True}
    assert len(calls) == 2
    mock_sleep.assert_awaited_once_with(2.0)


@pytest.mark.asyncio
async def test_5xx_exhausts_retries_and_raises():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            503, json={"code": "service_unavailable", "message": "down"}
        )

    http_client = _client_with_handler(handler)
    transport = NotionTransport(
        "secret-token-xyz", http_client=http_client, max_retries=1
    )

    with (
        patch("notion_db.http.asyncio.sleep", new=AsyncMock()),
        pytest.raises(NotionHTTPError) as excinfo,
    ):
        await transport.request("GET", "/pages/p1")

    assert excinfo.value.code == "service_unavailable"
    assert excinfo.value.status == 503
    assert len(calls) == 2  # initial attempt + 1 retry


@pytest.mark.asyncio
async def test_non_retryable_4xx_raises_immediately():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"code": "validation_error", "message": "bad"})

    http_client = _client_with_handler(handler)
    transport = NotionTransport("secret-token-xyz", http_client=http_client)

    with pytest.raises(NotionHTTPError) as excinfo:
        await transport.request("GET", "/pages/p1")

    assert excinfo.value.code == "validation_error"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_token_bucket_sleeps_when_exhausted():
    # A fake clock keeps this deterministic and instant: a plain no-op mock
    # for asyncio.sleep would never advance time, so the bucket would spin
    # (real wall-clock time) waiting for a token that never regenerates.
    fake_time = {"t": 0.0}

    async def fake_sleep(seconds: float) -> None:
        fake_time["t"] += seconds

    with (
        patch("notion_db.http.time.monotonic", side_effect=lambda: fake_time["t"]),
        patch(
            "notion_db.http.asyncio.sleep", new=AsyncMock(side_effect=fake_sleep)
        ) as mock_sleep,
    ):
        bucket = TokenBucket(rate=1.0, capacity=1.0)
        await bucket.acquire()  # consumes the only token, no sleep
        await bucket.acquire()  # must wait for a new token

    mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_logging_never_leaks_the_token(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "abc123"})

    http_client = _client_with_handler(handler)
    transport = NotionTransport("super-secret-token", http_client=http_client)

    with caplog.at_level("DEBUG", logger="notion_db.http"):
        await transport.request("GET", "/pages/abc123")

    assert "super-secret-token" not in caplog.text
