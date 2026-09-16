from __future__ import annotations

from datetime import date, datetime

import pytest

from notion_db.exceptions import NotionValidationError
from notion_db.properties import from_notion_property, to_notion_property


def test_title_round_trip():
    payload = to_notion_property("title", "Ship v0.1")
    assert payload == {"title": [{"type": "text", "text": {"content": "Ship v0.1"}}]}
    prop = {"type": "title", "title": [{"plain_text": "Ship v0.1"}]}
    assert from_notion_property("title", prop) == "Ship v0.1"


def test_rich_text_round_trip():
    payload = to_notion_property("rich_text", "notes here")
    assert payload == {"rich_text": [{"type": "text", "text": {"content": "notes here"}}]}
    prop = {"type": "rich_text", "rich_text": [{"plain_text": "notes here"}]}
    assert from_notion_property("rich_text", prop) == "notes here"


def test_number():
    assert to_notion_property("number", 42) == {"number": 42}
    assert from_notion_property("number", {"type": "number", "number": 42}) == 42


def test_select_round_trip():
    assert to_notion_property("select", "High") == {"select": {"name": "High"}}
    assert to_notion_property("select", None) == {"select": None}
    assert from_notion_property("select", {"type": "select", "select": {"name": "High"}}) == "High"
    assert from_notion_property("select", {"type": "select", "select": None}) is None


def test_multi_select_round_trip():
    assert to_notion_property("multi_select", ["a", "b"]) == {
        "multi_select": [{"name": "a"}, {"name": "b"}]
    }
    prop = {"type": "multi_select", "multi_select": [{"name": "a"}, {"name": "b"}]}
    assert from_notion_property("multi_select", prop) == ["a", "b"]


def test_status_round_trip():
    assert to_notion_property("status", "Done") == {"status": {"name": "Done"}}
    assert from_notion_property("status", {"type": "status", "status": {"name": "Done"}}) == "Done"


def test_checkbox_round_trip():
    assert to_notion_property("checkbox", True) == {"checkbox": True}
    assert from_notion_property("checkbox", {"type": "checkbox", "checkbox": True}) is True


def test_date_single_value_round_trip():
    d = date(2026, 1, 1)
    payload = to_notion_property("date", d)
    assert payload == {"date": {"start": "2026-01-01", "end": None}}
    prop = {"type": "date", "date": {"start": "2026-01-01", "end": None}}
    result = from_notion_property("date", prop)
    assert result == datetime(2026, 1, 1)


def test_date_range_round_trip():
    start, end = date(2026, 1, 1), date(2026, 1, 5)
    payload = to_notion_property("date", (start, end))
    assert payload == {"date": {"start": "2026-01-01", "end": "2026-01-05"}}
    prop = {"type": "date", "date": {"start": "2026-01-01", "end": "2026-01-05"}}
    result = from_notion_property("date", prop)
    assert result == (datetime(2026, 1, 1), datetime(2026, 1, 5))


def test_date_none():
    assert to_notion_property("date", None) == {"date": None}
    assert from_notion_property("date", {"type": "date", "date": None}) is None


def test_url_email_phone():
    assert to_notion_property("url", "https://x.test") == {"url": "https://x.test"}
    assert from_notion_property("url", {"type": "url", "url": "https://x.test"}) == "https://x.test"
    assert to_notion_property("email", "a@b.com") == {"email": "a@b.com"}
    assert to_notion_property("phone_number", "123") == {"phone_number": "123"}


def test_people_round_trip():
    assert to_notion_property("people", ["u1", "u2"]) == {
        "people": [{"id": "u1"}, {"id": "u2"}]
    }
    prop = {"type": "people", "people": [{"id": "u1"}, {"id": "u2"}]}
    assert from_notion_property("people", prop) == ["u1", "u2"]


def test_relation_round_trip():
    assert to_notion_property("relation", ["p1"]) == {"relation": [{"id": "p1"}]}
    prop = {"type": "relation", "relation": [{"id": "p1"}]}
    assert from_notion_property("relation", prop) == ["p1"]


def test_files_round_trip():
    payload = to_notion_property("files", ["https://x.test/a.png"])
    assert payload == {
        "files": [{"name": "a.png", "type": "external", "external": {"url": "https://x.test/a.png"}}]
    }
    prop = {
        "type": "files",
        "files": [{"name": "a.png", "external": {"url": "https://x.test/a.png"}}],
    }
    assert from_notion_property("files", prop) == ["https://x.test/a.png"]


def test_formula_unwraps_by_type():
    prop = {"type": "formula", "formula": {"type": "number", "number": 3.5}}
    assert from_notion_property("formula", prop) == 3.5


def test_rollup_array_of_numbers():
    prop = {
        "type": "rollup",
        "rollup": {
            "type": "array",
            "array": [
                {"type": "number", "number": 1},
                {"type": "number", "number": 2},
            ],
        },
    }
    assert from_notion_property("rollup", prop) == [1, 2]


def test_created_time_parses_iso():
    prop = {"type": "created_time", "created_time": "2026-01-01T00:00:00.000Z"}
    result = from_notion_property("created_time", prop)
    assert result.year == 2026 and result.month == 1 and result.day == 1


def test_created_by_returns_user_ref():
    prop = {"type": "created_by", "created_by": {"id": "u1", "name": "Alice"}}
    result = from_notion_property("created_by", prop)
    assert result == {"id": "u1", "name": "Alice"}


def test_writing_read_only_type_raises():
    with pytest.raises(NotionValidationError):
        to_notion_property("formula", 1)
    with pytest.raises(NotionValidationError):
        to_notion_property("created_time", "x")


def test_unsupported_type_raises():
    with pytest.raises(NotionValidationError):
        to_notion_property("nonexistent_type", "x")
