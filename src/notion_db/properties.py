"""Conversion between native Python values and Notion property-value JSON.

Each Notion property type has one entry in TO_NOTION (python value -> the
``{"<type>": ...}`` payload sent to the API) and one in FROM_NOTION (the full
property-value dict returned by the API -> a native Python value). Which
function to use for a given property *name* is decided at call time from the
database's schema (see client.py) rather than from any declared Python class,
so no per-property class needs to be written by users of this library.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from .exceptions import NotionValidationError

# Property types that Notion computes and never accepts writes for.
READ_ONLY_TYPES = frozenset(
    {
        "formula",
        "rollup",
        "created_time",
        "created_by",
        "last_edited_time",
        "last_edited_by",
        "unique_id",
    }
)


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _rich_text_to_plain(rich_text: list[dict]) -> str:
    return "".join(item.get("plain_text", "") for item in rich_text)


def _plain_to_rich_text(value: str) -> list[dict]:
    if not value:
        return []
    return [{"type": "text", "text": {"content": value}}]


def _to_title(value: Any) -> dict:
    return {"title": _plain_to_rich_text(str(value))}


def _from_title(prop: dict) -> str:
    return _rich_text_to_plain(prop.get("title") or [])


def _to_rich_text(value: Any) -> dict:
    return {"rich_text": _plain_to_rich_text(str(value))}


def _from_rich_text(prop: dict) -> str:
    return _rich_text_to_plain(prop.get("rich_text") or [])


def _to_number(value: Any) -> dict:
    return {"number": value}


def _from_number(prop: dict) -> float | int | None:
    return prop.get("number")


def _to_select(value: Any) -> dict:
    return {"select": {"name": value} if value is not None else None}


def _from_select(prop: dict) -> str | None:
    select = prop.get("select")
    return select["name"] if select else None


def _to_multi_select(value: Any) -> dict:
    return {"multi_select": [{"name": v} for v in (value or [])]}


def _from_multi_select(prop: dict) -> list[str]:
    return [item["name"] for item in prop.get("multi_select") or []]


def _to_status(value: Any) -> dict:
    return {"status": {"name": value} if value is not None else None}


def _from_status(prop: dict) -> str | None:
    status = prop.get("status")
    return status["name"] if status else None


def _iso(value: date | datetime) -> str:
    return value.isoformat()


def _to_date(value: Any) -> dict:
    if value is None:
        return {"date": None}
    if isinstance(value, tuple):
        start, end = value
        return {
            "date": {
                "start": _iso(start),
                "end": _iso(end) if end is not None else None,
            }
        }
    return {"date": {"start": _iso(value), "end": None}}


def _from_date(prop: dict) -> date | datetime | tuple | None:
    d = prop.get("date")
    if d is None:
        return None
    start = _parse_iso(d["start"])
    end = _parse_iso(d["end"]) if d.get("end") else None
    return (start, end) if end is not None else start


def _to_checkbox(value: Any) -> dict:
    return {"checkbox": bool(value)}


def _from_checkbox(prop: dict) -> bool:
    return bool(prop.get("checkbox"))


def _to_url(value: Any) -> dict:
    return {"url": value}


def _from_url(prop: dict) -> str | None:
    return prop.get("url")


def _to_email(value: Any) -> dict:
    return {"email": value}


def _from_email(prop: dict) -> str | None:
    return prop.get("email")


def _to_phone_number(value: Any) -> dict:
    return {"phone_number": value}


def _from_phone_number(prop: dict) -> str | None:
    return prop.get("phone_number")


def _to_people(value: Any) -> dict:
    return {"people": [{"id": user_id} for user_id in (value or [])]}


def _from_people(prop: dict) -> list[str]:
    return [person["id"] for person in prop.get("people") or []]


def _to_relation(value: Any) -> dict:
    return {"relation": [{"id": page_id} for page_id in (value or [])]}


def _from_relation(prop: dict) -> list[str]:
    return [item["id"] for item in prop.get("relation") or []]


def _to_files(value: Any) -> dict:
    return {
        "files": [
            {
                "name": url.rsplit("/", 1)[-1] or url,
                "type": "external",
                "external": {"url": url},
            }
            for url in (value or [])
        ]
    }


def _from_files(prop: dict) -> list[str]:
    urls = []
    for item in prop.get("files") or []:
        if "external" in item:
            urls.append(item["external"]["url"])
        elif "file" in item:
            urls.append(item["file"]["url"])
    return urls


def _from_formula(prop: dict) -> Any:
    formula = prop["formula"]
    return formula.get(formula["type"])


def _from_rollup_item(item: dict) -> Any:
    from_fn = FROM_NOTION.get(item.get("type", ""))
    return from_fn(item) if from_fn else item


def _from_rollup(prop: dict) -> Any:
    rollup = prop["rollup"]
    rollup_type = rollup["type"]
    if rollup_type == "array":
        return [_from_rollup_item(item) for item in rollup["array"]]
    return rollup.get(rollup_type)


def _from_created_time(prop: dict) -> datetime:
    return _parse_iso(prop["created_time"])


def _from_last_edited_time(prop: dict) -> datetime:
    return _parse_iso(prop["last_edited_time"])


def _from_user_ref(key: str) -> Callable[[dict], dict]:
    def _from(prop: dict) -> dict:
        user = prop[key]
        return {"id": user.get("id"), "name": user.get("name")}

    return _from


TO_NOTION: dict[str, Callable[[Any], dict]] = {
    "title": _to_title,
    "rich_text": _to_rich_text,
    "number": _to_number,
    "select": _to_select,
    "multi_select": _to_multi_select,
    "status": _to_status,
    "date": _to_date,
    "checkbox": _to_checkbox,
    "url": _to_url,
    "email": _to_email,
    "phone_number": _to_phone_number,
    "people": _to_people,
    "relation": _to_relation,
    "files": _to_files,
}

FROM_NOTION: dict[str, Callable[[dict], Any]] = {
    "title": _from_title,
    "rich_text": _from_rich_text,
    "number": _from_number,
    "select": _from_select,
    "multi_select": _from_multi_select,
    "status": _from_status,
    "date": _from_date,
    "checkbox": _from_checkbox,
    "url": _from_url,
    "email": _from_email,
    "phone_number": _from_phone_number,
    "people": _from_people,
    "relation": _from_relation,
    "files": _from_files,
    "formula": _from_formula,
    "rollup": _from_rollup,
    "created_time": _from_created_time,
    "last_edited_time": _from_last_edited_time,
    "created_by": _from_user_ref("created_by"),
    "last_edited_by": _from_user_ref("last_edited_by"),
}


def to_notion_property(notion_type: str, value: Any) -> dict:
    if notion_type in READ_ONLY_TYPES:
        raise NotionValidationError(
            f"property type {notion_type!r} is read-only and cannot be written"
        )
    to_fn = TO_NOTION.get(notion_type)
    if to_fn is None:
        raise NotionValidationError(f"unsupported property type {notion_type!r}")
    return to_fn(value)


def from_notion_property(notion_type: str, prop: dict) -> Any:
    from_fn = FROM_NOTION.get(notion_type)
    if from_fn is None:
        return None
    return from_fn(prop)
