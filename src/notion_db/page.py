"""Lightweight, dict-like result object for a Notion page — no declared model required."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from .properties import from_notion_property


@dataclass
class Page:
    id: str
    url: str | None
    archived: bool
    properties: dict[str, Any] = field(default_factory=dict)
    raw: dict = field(default_factory=dict, repr=False)

    def __getitem__(self, name: str) -> Any:
        return self.properties[name]

    def __contains__(self, name: str) -> bool:
        return name in self.properties

    def __iter__(self) -> Iterator[str]:
        return iter(self.properties)

    def get(self, name: str, default: Any = None) -> Any:
        return self.properties.get(name, default)

    @classmethod
    def from_raw(cls, raw: dict) -> "Page":
        """Build a Page from a raw Notion page object. The type of each
        property is read straight off the payload (every Notion property
        value carries its own "type" field), so no schema lookup is needed
        just to parse a response."""
        properties: dict[str, Any] = {}
        for name, prop in raw.get("properties", {}).items():
            notion_type = prop.get("type")
            if notion_type is None:
                continue
            properties[name] = from_notion_property(notion_type, prop)
        return cls(
            id=raw["id"],
            url=raw.get("url"),
            archived=raw.get("archived", False),
            properties=properties,
            raw=raw,
        )
