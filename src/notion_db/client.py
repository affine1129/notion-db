"""NotionDB / AsyncNotionDB: schema-aware wrappers around one Notion database.

AsyncNotionDB is the core implementation -- every method is `async def` and
talks to notion_client.AsyncClient directly. NotionDB (sync) holds one
AsyncNotionDB internally and just runs its async methods to completion via
run_sync(); the schema resolution, property conversion, filter/sort
compilation and pagination logic lives exactly once, in AsyncNotionDB.
"""

from __future__ import annotations

import os
from typing import Any

from notion_client import AsyncClient
from notion_client.errors import NotionClientErrorBase

from ._sync import run_sync
from .exceptions import NotionDBError, NotionValidationError, translate_error
from .filters import FilterExpr
from .page import Page
from .properties import READ_ONLY_TYPES, to_notion_property
from .query import AsyncQuery, Query, compile_query_kwargs

_ENV_TOKEN = "NOTION_TOKEN"


def _resolve_token(token: str | None) -> str:
    token = token or os.environ.get(_ENV_TOKEN)
    if not token:
        raise NotionDBError(
            f"no Notion token given; pass token=... or set the {_ENV_TOKEN} environment variable"
        )
    return token


class AsyncNotionDB:
    """Async, schema-aware wrapper around one Notion database."""

    def __init__(
        self,
        database_id: str,
        *,
        token: str | None = None,
        data_source_id: str | None = None,
        client: AsyncClient | None = None,
    ) -> None:
        self.database_id = database_id
        self._client = client or AsyncClient(auth=_resolve_token(token))
        self._data_source_id = data_source_id
        self._schema: dict[str, str] | None = None

    async def _ensure_schema(self) -> None:
        if self._schema is not None:
            return
        try:
            if self._data_source_id is None:
                database = await self._client.databases.retrieve(database_id=self.database_id)
                data_sources = database.get("data_sources", [])
                if len(data_sources) != 1:
                    raise NotionDBError(
                        f"database {self.database_id!r} has {len(data_sources)} data sources; "
                        "pass data_source_id=... explicitly to disambiguate"
                    )
                self._data_source_id = data_sources[0]["id"]
            data_source = await self._client.data_sources.retrieve(data_source_id=self._data_source_id)
        except NotionClientErrorBase as exc:
            translate_error(exc)
        self._schema = {name: prop["type"] for name, prop in data_source.get("properties", {}).items()}

    def _build_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        assert self._schema is not None
        payload: dict[str, Any] = {}
        for name, value in properties.items():
            if name not in self._schema:
                raise NotionValidationError(f"unknown property {name!r} for database {self.database_id!r}")
            notion_type = self._schema[name]
            if notion_type in READ_ONLY_TYPES:
                raise NotionValidationError(f"property {name!r} is read-only ({notion_type})")
            payload[name] = to_notion_property(notion_type, value)
        return payload

    async def create(self, properties: dict[str, Any]) -> Page:
        await self._ensure_schema()
        payload = self._build_properties(properties)
        try:
            raw = await self._client.pages.create(
                parent={"type": "data_source_id", "data_source_id": self._data_source_id},
                properties=payload,
            )
        except NotionClientErrorBase as exc:
            translate_error(exc)
        return Page.from_raw(raw)

    async def get(self, page_id: str) -> Page:
        try:
            raw = await self._client.pages.retrieve(page_id=page_id)
        except NotionClientErrorBase as exc:
            translate_error(exc)
        return Page.from_raw(raw)

    async def update(self, page_id: str, properties: dict[str, Any]) -> Page:
        await self._ensure_schema()
        payload = self._build_properties(properties)
        try:
            raw = await self._client.pages.update(page_id=page_id, properties=payload)
        except NotionClientErrorBase as exc:
            translate_error(exc)
        return Page.from_raw(raw)

    async def delete(self, page_id: str) -> None:
        """Archive the page. Notion has no hard delete via the API."""
        try:
            await self._client.pages.update(page_id=page_id, archived=True)
        except NotionClientErrorBase as exc:
            translate_error(exc)

    async def query(
        self,
        *,
        filter: FilterExpr | dict[str, Any] | None = None,  # noqa: A002
        sort: str | list[Any] | None = None,
        limit: int | None = None,
        page_size: int = 100,
    ) -> AsyncQuery:
        await self._ensure_schema()
        assert self._schema is not None and self._data_source_id is not None
        kwargs = compile_query_kwargs(self._data_source_id, self._schema, filter, sort, page_size)
        return AsyncQuery(query_fn=self._client.data_sources.query, kwargs=kwargs, limit=limit)


class NotionDB:
    """Sync, schema-aware wrapper around one Notion database.

    A thin wrapper around AsyncNotionDB: every method just runs the matching
    async method to completion (one run_sync() call per method), so the real
    logic lives exactly once.
    """

    def __init__(
        self,
        database_id: str,
        *,
        token: str | None = None,
        data_source_id: str | None = None,
        client: AsyncClient | None = None,
    ) -> None:
        self._async = AsyncNotionDB(database_id, token=token, data_source_id=data_source_id, client=client)

    @property
    def database_id(self) -> str:
        return self._async.database_id

    def create(self, properties: dict[str, Any]) -> Page:
        return run_sync(self._async.create(properties))

    def get(self, page_id: str) -> Page:
        return run_sync(self._async.get(page_id))

    def update(self, page_id: str, properties: dict[str, Any]) -> Page:
        return run_sync(self._async.update(page_id, properties))

    def delete(self, page_id: str) -> None:
        run_sync(self._async.delete(page_id))

    def query(
        self,
        *,
        filter: FilterExpr | dict[str, Any] | None = None,  # noqa: A002
        sort: str | list[Any] | None = None,
        limit: int | None = None,
        page_size: int = 100,
    ) -> Query:
        async def _collect() -> list[Page]:
            async_query = await self._async.query(filter=filter, sort=sort, limit=limit, page_size=page_size)
            return await async_query.all()

        return Query(run_sync(_collect()))
