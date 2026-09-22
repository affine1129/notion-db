"""notion_db: a small, schema-aware wrapper around the Notion API.

No model classes to declare -- point NotionDB at a database id and use
plain dicts for property names/values; types are resolved automatically
from the database's own schema.
"""

from .client import AsyncNotionDB, NotionDB
from .exceptions import (
    NotionAPIError,
    NotionAuthError,
    NotionDBError,
    NotionNotFoundError,
    NotionRateLimitError,
    NotionValidationError,
)
from .filters import F, FilterExpr
from .page import Page
from .query import AsyncQuery, Query

__all__ = [
    "AsyncNotionDB",
    "AsyncQuery",
    "F",
    "FilterExpr",
    "NotionAPIError",
    "NotionAuthError",
    "NotionDB",
    "NotionDBError",
    "NotionNotFoundError",
    "NotionRateLimitError",
    "NotionValidationError",
    "Page",
    "Query",
]
