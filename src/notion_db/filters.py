"""Query filters: a tiny expression builder (F(...)) plus a plain-dict shortcut.

Simple equality filters need no import at all:

    db.query(filter={"Status": "Done"})

Anything richer uses F(name), whose comparisons build a FilterExpr tree that
combines with & (and) / | (or):

    db.query(filter=(F("Status") == "In Progress") & (F("Priority") == "High"))

F() itself doesn't know property types -- the tree is only resolved against a
database's schema (name -> Notion type) when compiled via .to_json(schema),
which happens when a Query actually runs.
"""

from __future__ import annotations

from typing import Any


class FilterExpr:
    """A leaf condition, or an and/or group of them."""

    def __init__(
        self,
        *,
        property_name: str | None = None,
        condition: str | None = None,
        value: Any = None,
        compound_op: str | None = None,
        children: list[FilterExpr] | None = None,
    ) -> None:
        self.property_name = property_name
        self.condition = condition
        self.value = value
        self.compound_op = compound_op
        self.children = children or []

    def __and__(self, other: FilterExpr) -> FilterExpr:
        return self._combine("and", other)

    def __or__(self, other: FilterExpr) -> FilterExpr:
        return self._combine("or", other)

    def _combine(self, op: str, other: FilterExpr) -> FilterExpr:
        if not isinstance(other, FilterExpr):
            raise TypeError(
                "did you forget parentheses around each comparison? "
                "write (F('A') == 1) & (F('B') == 2), not F('A') == 1 & F('B') == 2"
            )
        left = self.children if self.compound_op == op else [self]
        right = other.children if other.compound_op == op else [other]
        return FilterExpr(compound_op=op, children=[*left, *right])

    def __bool__(self) -> bool:
        raise TypeError(
            "a filter expression cannot be used as a bool -- did you forget "
            "parentheses around each comparison? write (F('A') == 1) & (F('B') == 2)"
        )

    def to_json(self, schema: dict[str, str]) -> dict:
        if self.compound_op is not None:
            return {
                self.compound_op: [child.to_json(schema) for child in self.children]
            }
        if self.property_name not in schema:
            raise KeyError(f"unknown property {self.property_name!r} for this database")
        notion_type = schema[self.property_name]
        return {
            "property": self.property_name,
            notion_type: {self.condition: self.value},
        }


def _isoify(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


class FieldRef:
    """F("Property Name") -- builds FilterExpr leaves via comparisons/methods."""

    def __init__(self, name: str) -> None:
        self.name = name

    def _leaf(self, condition: str, value: Any) -> FilterExpr:
        return FilterExpr(property_name=self.name, condition=condition, value=value)

    def __eq__(self, other: object) -> FilterExpr:  # type: ignore[override]
        return self._leaf("equals", other)

    def __ne__(self, other: object) -> FilterExpr:  # type: ignore[override]
        return self._leaf("does_not_equal", other)

    def __gt__(self, other: Any) -> FilterExpr:
        return self._leaf("greater_than", other)

    def __lt__(self, other: Any) -> FilterExpr:
        return self._leaf("less_than", other)

    def __ge__(self, other: Any) -> FilterExpr:
        return self._leaf("greater_than_or_equal_to", other)

    def __le__(self, other: Any) -> FilterExpr:
        return self._leaf("less_than_or_equal_to", other)

    def contains(self, other: Any) -> FilterExpr:
        return self._leaf("contains", other)

    def does_not_contain(self, other: Any) -> FilterExpr:
        return self._leaf("does_not_contain", other)

    def starts_with(self, other: Any) -> FilterExpr:
        return self._leaf("starts_with", other)

    def ends_with(self, other: Any) -> FilterExpr:
        return self._leaf("ends_with", other)

    def is_empty(self) -> FilterExpr:
        return self._leaf("is_empty", True)

    def is_not_empty(self) -> FilterExpr:
        return self._leaf("is_not_empty", True)

    def before(self, other: Any) -> FilterExpr:
        return self._leaf("before", _isoify(other))

    def after(self, other: Any) -> FilterExpr:
        return self._leaf("after", _isoify(other))

    def on_or_before(self, other: Any) -> FilterExpr:
        return self._leaf("on_or_before", _isoify(other))

    def on_or_after(self, other: Any) -> FilterExpr:
        return self._leaf("on_or_after", _isoify(other))

    def __hash__(self) -> int:
        return hash(("FieldRef", self.name))


def F(name: str) -> FieldRef:
    return FieldRef(name)


def dict_to_filter(filter_dict: dict[str, Any]) -> FilterExpr:
    """Turn {"A": 1, "B": 2} into (F("A") == 1) & (F("B") == 2)."""
    expr: FilterExpr | None = None
    for name, value in filter_dict.items():
        leaf = F(name) == value
        expr = leaf if expr is None else expr & leaf
    assert expr is not None
    return expr


def compile_filter(
    filter_: FilterExpr | dict[str, Any] | None, schema: dict[str, str]
) -> dict | None:
    if filter_ is None:
        return None
    if isinstance(filter_, dict):
        if not filter_:
            return None
        filter_ = dict_to_filter(filter_)
    if not isinstance(filter_, FilterExpr):
        raise TypeError(
            f"filter must be a dict or FilterExpr, got {type(filter_).__name__}"
        )
    return filter_.to_json(schema)
