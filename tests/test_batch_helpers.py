from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock

import pytest

from notion_db.client import AsyncNotionDB, NotionDB
from notion_db.exceptions import NotionDBError, NotionValidationError
from notion_db.page import Page

from conftest import DATABASE_ID, make_raw_page


def _title_of(properties: dict) -> str:
    return properties["Name"]["title"][0]["text"]["content"]


@pytest.mark.asyncio
async def test_create_many_returns_pages_in_order(mock_client):
    async def _create_side_effect(*, parent, properties):
        name = _title_of(properties)
        return make_raw_page(f"p-{name}", name)

    mock_client.pages.create = AsyncMock(side_effect=_create_side_effect)
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    results = await db.create_many([{"Name": "Task A"}, {"Name": "Task B"}])

    assert [r["Name"] for r in results] == ["Task A", "Task B"]
    assert all(isinstance(r, Page) for r in results)


@pytest.mark.asyncio
async def test_create_many_is_best_effort_on_partial_failure(mock_client):
    async def _create_side_effect(*, parent, properties):
        name = _title_of(properties)
        return make_raw_page(f"p-{name}", name)

    mock_client.pages.create = AsyncMock(side_effect=_create_side_effect)
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    results = await db.create_many(
        [{"Name": "Task A"}, {"UnknownProperty": "x"}, {"Name": "Task C"}]
    )

    assert isinstance(results[0], Page)
    assert results[0]["Name"] == "Task A"
    assert isinstance(results[1], NotionValidationError)
    assert isinstance(results[2], Page)
    assert results[2]["Name"] == "Task C"


@pytest.mark.asyncio
async def test_update_many_returns_pages_in_order(mock_client):
    async def _update_side_effect(*, page_id, properties=None, archived=None):
        name = _title_of(properties)
        return make_raw_page(page_id, name)

    mock_client.pages.update = AsyncMock(side_effect=_update_side_effect)
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    results = await db.update_many([("p1", {"Name": "New A"}), ("p2", {"Name": "New B"})])

    assert [r["Name"] for r in results] == ["New A", "New B"]


@pytest.mark.asyncio
async def test_update_many_is_best_effort_on_partial_failure(mock_client):
    async def _update_side_effect(*, page_id, properties=None, archived=None):
        name = _title_of(properties)
        return make_raw_page(page_id, name)

    mock_client.pages.update = AsyncMock(side_effect=_update_side_effect)
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    results = await db.update_many([("p1", {"Name": "New A"}), ("p2", {"UnknownProperty": "y"})])

    assert isinstance(results[0], Page)
    assert isinstance(results[1], NotionDBError)


@pytest.mark.asyncio
async def test_create_many_respects_max_concurrency(mock_client):
    live = 0
    peak = 0

    async def _create_side_effect(*, parent, properties):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.01)
        live -= 1
        name = _title_of(properties)
        return make_raw_page(f"p-{name}", name)

    mock_client.pages.create = AsyncMock(side_effect=_create_side_effect)
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    items = [{"Name": f"Task {i}"} for i in range(10)]
    await db.create_many(items, max_concurrency=3)

    assert peak <= 3


def test_sync_create_many_and_update_many(mock_client):
    async def _create_side_effect(*, parent, properties):
        name = _title_of(properties)
        return make_raw_page(f"p-{name}", name)

    async def _update_side_effect(*, page_id, properties=None, archived=None):
        name = _title_of(properties)
        return make_raw_page(page_id, name)

    mock_client.pages.create = AsyncMock(side_effect=_create_side_effect)
    mock_client.pages.update = AsyncMock(side_effect=_update_side_effect)
    db = NotionDB(DATABASE_ID, client=mock_client)

    created = db.create_many([{"Name": "Task A"}, {"Name": "Task B"}])
    assert [r["Name"] for r in created] == ["Task A", "Task B"]

    updated = db.update_many([("p1", {"Name": "New A"})])
    assert updated[0]["Name"] == "New A"
