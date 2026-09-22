from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from conftest import DATABASE_ID, make_raw_page, paginated_side_effect

from notion_db.client import AsyncNotionDB, NotionDB


def _three_pages() -> list[list[dict]]:
    return [
        [make_raw_page("p1", "Task 1"), make_raw_page("p2", "Task 2")],
        [make_raw_page("p3", "Task 3")],
        [make_raw_page("p4", "Task 4"), make_raw_page("p5", "Task 5")],
    ]


@pytest.mark.asyncio
async def test_async_query_iterates_across_all_pages(mock_client):
    mock_client.data_sources.query = AsyncMock(
        side_effect=paginated_side_effect(_three_pages())
    )
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    query = await db.query()
    names = [page["Name"] async for page in query]

    assert names == ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"]


@pytest.mark.asyncio
async def test_async_query_all_and_first(mock_client):
    mock_client.data_sources.query = AsyncMock(
        side_effect=paginated_side_effect(_three_pages())
    )
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    query = await db.query()
    assert len(await query.all()) == 5

    query2 = await db.query()
    first = await query2.first()
    assert first["Name"] == "Task 1"


@pytest.mark.asyncio
async def test_async_query_respects_limit(mock_client):
    mock_client.data_sources.query = AsyncMock(
        side_effect=paginated_side_effect(_three_pages())
    )
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    query = await db.query(limit=3)
    names = [page["Name"] async for page in query]
    assert names == ["Task 1", "Task 2", "Task 3"]


def test_sync_query_iterates_across_all_pages(mock_client):
    mock_client.data_sources.query = AsyncMock(
        side_effect=paginated_side_effect(_three_pages())
    )
    db = NotionDB(DATABASE_ID, client=mock_client)

    names = [page["Name"] for page in db.query()]
    assert names == ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"]


def test_sync_query_first_and_len(mock_client):
    mock_client.data_sources.query = AsyncMock(
        side_effect=paginated_side_effect(_three_pages())
    )
    db = NotionDB(DATABASE_ID, client=mock_client)

    result = db.query()
    assert len(result) == 5
    assert result.first()["Name"] == "Task 1"
