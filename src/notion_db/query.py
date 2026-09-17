"""Iterable, auto-paginating query results.

AsyncQuery drives its own start_cursor/has_more/next_cursor bookkeeping over
the injected query function. Query (used by the sync NotionDB) is a plain
materialized list: the sync facade fully collects a query's pages in a
single run_sync() call rather than opening one event loop per page.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Callable, Iterator

from .filters import FilterExpr, compile_filter
from .page import Page

Filter = "FilterExpr | dict[str, Any] | None"
Sort = "str | list[str | tuple[str, str]] | None"


def compile_sort(sort: Any) -> list[dict] | None:
    if sort is None:
        return None
    items = [sort] if isinstance(sort, str) else sort
    compiled = []
    for item in items:
        name, direction = (item, "asc") if isinstance(item, str) else item
        compiled.append(
            {
                "property": name,
                "direction": "ascending" if direction in ("asc", "ascending") else "descending",
            }
        )
    return compiled


def compile_query_kwargs(
    data_source_id: str,
    schema: dict[str, str],
    filter_: Any,
    sort: Any,
    page_size: int,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"data_source_id": data_source_id, "page_size": page_size}
    compiled_filter = compile_filter(filter_, schema)
    if compiled_filter is not None:
        kwargs["filter"] = compiled_filter
    compiled_sort = compile_sort(sort)
    if compiled_sort is not None:
        kwargs["sorts"] = compiled_sort
    return kwargs


class Query:
    """A fully-fetched, iterable list of pages (used by the sync NotionDB)."""

    def __init__(self, pages: list[Page]) -> None:
        self._pages = pages

    def __iter__(self) -> Iterator[Page]:
        return iter(self._pages)

    def __len__(self) -> int:
        return len(self._pages)

    def all(self) -> list[Page]:
        return list(self._pages)

    def first(self) -> Page | None:
        return self._pages[0] if self._pages else None


class AsyncQuery:
    """A lazily-paginated async iterator over pages (used by AsyncNotionDB)."""

    def __init__(
        self,
        *,
        query_fn: Callable[..., Any],
        kwargs: dict[str, Any],
        limit: int | None = None,
    ) -> None:
        self._query_fn = query_fn
        self._kwargs = kwargs
        self._limit = limit

    async def __aiter__(self) -> AsyncIterator[Page]:
        kwargs = dict(self._kwargs)
        next_cursor = kwargs.pop("start_cursor", None)
        count = 0
        while True:
            if self._limit is not None and count >= self._limit:
                return
            response = await self._query_fn(**kwargs, start_cursor=next_cursor)
            for raw_page in response.get("results", []):
                if self._limit is not None and count >= self._limit:
                    return
                yield Page.from_raw(raw_page)
                count += 1
            next_cursor = response.get("next_cursor")
            if not response.get("has_more") or next_cursor is None:
                return

    async def all(self) -> list[Page]:
        return [page async for page in self]

    async def first(self) -> Page | None:
        async for page in self:
            return page
        return None
