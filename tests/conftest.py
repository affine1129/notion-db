from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

DATABASE_ID = "db-123"
DATA_SOURCE_ID = "ds-456"

DATABASE_RESPONSE = {
    "id": DATABASE_ID,
    "data_sources": [{"id": DATA_SOURCE_ID, "name": "Tasks"}],
}

DATA_SOURCE_RESPONSE = {
    "id": DATA_SOURCE_ID,
    "properties": {
        "Name": {"id": "title", "name": "Name", "type": "title", "title": {}},
        "Status": {"id": "st1", "name": "Status", "type": "status", "status": {}},
        "Priority": {"id": "pr1", "name": "Priority", "type": "select", "select": {}},
        "Tags": {"id": "tg1", "name": "Tags", "type": "multi_select", "multi_select": {}},
        "Due Date": {"id": "dd1", "name": "Due Date", "type": "date", "date": {}},
        "Done": {"id": "dn1", "name": "Done", "type": "checkbox", "checkbox": {}},
        "Estimate": {"id": "es1", "name": "Estimate", "type": "number", "number": {}},
        "Created": {"id": "cr1", "name": "Created", "type": "created_time", "created_time": {}},
    },
}


def make_raw_page(page_id: str, name: str, status: str = "Not Started", archived: bool = False) -> dict[str, Any]:
    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
        "archived": archived,
        "properties": {
            "Name": {
                "id": "title",
                "type": "title",
                "title": [{"type": "text", "text": {"content": name}, "plain_text": name}],
            },
            "Status": {"id": "st1", "type": "status", "status": {"name": status}},
        },
    }


def paginated_side_effect(pages: list[list[dict]]):
    """A data_sources.query side_effect that respects start_cursor like the real API."""

    def _side_effect(**kwargs: Any) -> dict:
        cursor = kwargs.get("start_cursor")
        index = 0 if cursor is None else int(cursor)
        results = pages[index]
        has_more = index + 1 < len(pages)
        return {
            "results": results,
            "has_more": has_more,
            "next_cursor": str(index + 1) if has_more else None,
        }

    return _side_effect


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock(name="AsyncClient")
    client.databases.retrieve = AsyncMock(return_value=DATABASE_RESPONSE)
    client.data_sources.retrieve = AsyncMock(return_value=DATA_SOURCE_RESPONSE)
    client.data_sources.query = AsyncMock(
        return_value={"results": [], "has_more": False, "next_cursor": None}
    )
    client.pages.create = AsyncMock()
    client.pages.retrieve = AsyncMock()
    client.pages.update = AsyncMock()
    return client
