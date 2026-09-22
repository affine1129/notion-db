from __future__ import annotations

import pytest
from conftest import DATA_SOURCE_ID, DATABASE_ID, make_raw_page

from notion_db.client import AsyncNotionDB
from notion_db.exceptions import NotionValidationError


@pytest.mark.asyncio
async def test_create_sends_parent_and_converted_properties(mock_client):
    mock_client.pages.create.return_value = make_raw_page(
        "p1", "Ship v0.1", "Not Started"
    )
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    page = await db.create({"Name": "Ship v0.1", "Status": "Not Started"})

    assert page.id == "p1"
    assert page["Name"] == "Ship v0.1"

    _, kwargs = mock_client.pages.create.call_args
    assert kwargs["parent"] == {
        "type": "data_source_id",
        "data_source_id": DATA_SOURCE_ID,
    }
    assert kwargs["properties"]["Status"] == {"status": {"name": "Not Started"}}


@pytest.mark.asyncio
async def test_get_returns_page(mock_client):
    mock_client.pages.retrieve.return_value = make_raw_page("p1", "Task 1", "Done")
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    page = await db.get("p1")

    assert page.id == "p1"
    assert page["Status"] == "Done"


@pytest.mark.asyncio
async def test_update_sends_only_given_properties(mock_client):
    mock_client.pages.update.return_value = make_raw_page("p1", "Task 1", "Done")
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    page = await db.update("p1", {"Status": "Done"})

    assert page["Status"] == "Done"
    _, kwargs = mock_client.pages.update.call_args
    assert kwargs["properties"] == {"Status": {"status": {"name": "Done"}}}


@pytest.mark.asyncio
async def test_delete_archives_the_page(mock_client):
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    await db.delete("p1")

    mock_client.pages.update.assert_awaited_once_with(page_id="p1", archived=True)


@pytest.mark.asyncio
async def test_unknown_property_raises(mock_client):
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)
    with pytest.raises(NotionValidationError):
        await db.create({"NoSuchProperty": "x"})


@pytest.mark.asyncio
async def test_schema_is_fetched_only_once(mock_client):
    mock_client.pages.create.return_value = make_raw_page("p1", "A")
    db = AsyncNotionDB(DATABASE_ID, client=mock_client)

    await db.create({"Name": "A"})
    await db.create({"Name": "B"})

    assert mock_client.databases.retrieve.await_count == 1
    assert mock_client.data_sources.retrieve.await_count == 1
