"""Bridge for running the async core (AsyncNotionDB) from the sync facade (NotionDB)."""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine, TypeVar

from .exceptions import NotionDBError

T = TypeVar("T")


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise NotionDBError(
        "NotionDB (sync) cannot be used from inside a running event loop; use AsyncNotionDB instead"
    )
