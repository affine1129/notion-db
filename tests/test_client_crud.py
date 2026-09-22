from __future__ import annotations

import pytest
from conftest import DATA_SOURCE_ID, DATABASE_ID, make_raw_page

from notion_db.client import NotionDB
from notion_db.exceptions import NotionDBError, NotionValidationError


def test_create_sends_parent_and_converted_properties(mock_client):
    mock_client.pages.create.return_value = make_raw_page(
        "p1", "Ship v0.1", "Not Started"
    )
    db = NotionDB(DATABASE_ID, client=mock_client)

    page = db.create({"Name": "Ship v0.1", "Status": "Not Started"})

    assert page.id == "p1"
    assert page["Name"] == "Ship v0.1"
    assert page["Status"] == "Not Started"

    _, kwargs = mock_client.pages.create.call_args
    assert kwargs["parent"] == {
        "type": "data_source_id",
        "data_source_id": DATA_SOURCE_ID,
    }
    assert kwargs["properties"]["Name"] == {
        "title": [{"type": "text", "text": {"content": "Ship v0.1"}}]
    }
    assert kwargs["properties"]["Status"] == {"status": {"name": "Not Started"}}


def test_get_returns_page(mock_client):
    mock_client.pages.retrieve.return_value = make_raw_page("p1", "Task 1", "Done")
    db = NotionDB(DATABASE_ID, client=mock_client)

    page = db.get("p1")

    assert page.id == "p1"
    assert page["Status"] == "Done"
    mock_client.pages.retrieve.assert_awaited_once_with(page_id="p1")


def test_update_sends_only_given_properties(mock_client):
    mock_client.pages.update.return_value = make_raw_page("p1", "Task 1", "Done")
    db = NotionDB(DATABASE_ID, client=mock_client)

    page = db.update("p1", {"Status": "Done"})

    assert page["Status"] == "Done"
    _, kwargs = mock_client.pages.update.call_args
    assert kwargs["page_id"] == "p1"
    assert kwargs["properties"] == {"Status": {"status": {"name": "Done"}}}


def test_delete_archives_the_page(mock_client):
    db = NotionDB(DATABASE_ID, client=mock_client)

    db.delete("p1")

    mock_client.pages.update.assert_awaited_once_with(page_id="p1", archived=True)


def test_unknown_property_raises(mock_client):
    db = NotionDB(DATABASE_ID, client=mock_client)
    with pytest.raises(NotionValidationError):
        db.create({"NoSuchProperty": "x"})


def test_writing_read_only_property_raises(mock_client):
    db = NotionDB(DATABASE_ID, client=mock_client)
    with pytest.raises(NotionValidationError):
        db.create({"Created": "2026-01-01"})


def test_multiple_data_sources_requires_explicit_id(mock_client):
    mock_client.databases.retrieve.return_value = {
        "id": DATABASE_ID,
        "data_sources": [{"id": "ds-1", "name": "A"}, {"id": "ds-2", "name": "B"}],
    }
    db = NotionDB(DATABASE_ID, client=mock_client)
    with pytest.raises(NotionDBError):
        db.create({"Name": "x"})
