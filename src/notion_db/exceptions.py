"""Exception hierarchy for notion_db, wrapping notion_client errors."""

from __future__ import annotations

from typing import NoReturn


class NotionDBError(Exception):
    """Base class for all errors raised by notion_db."""


class NotionAuthError(NotionDBError):
    """The Notion token is missing, invalid, or lacks access to the resource."""


class NotionNotFoundError(NotionDBError):
    """The requested database or page does not exist (or is not shared with the integration)."""


class NotionRateLimitError(NotionDBError):
    """The Notion API rate limit was exceeded after notion_client's own retries were exhausted."""


class NotionValidationError(NotionDBError):
    """The request did not match the database schema, e.g. an unknown or read-only property."""


class NotionAPIError(NotionDBError):
    """Catch-all wrapper for any other Notion API or transport error."""


_API_CODE_TO_ERROR: dict[str, type[NotionDBError]] = {
    "unauthorized": NotionAuthError,
    "restricted_resource": NotionAuthError,
    "object_not_found": NotionNotFoundError,
    "rate_limited": NotionRateLimitError,
    "validation_error": NotionValidationError,
    "invalid_json": NotionValidationError,
    "invalid_request": NotionValidationError,
    "invalid_request_url": NotionValidationError,
    "conflict_error": NotionAPIError,
    "internal_server_error": NotionAPIError,
    "service_unavailable": NotionAPIError,
    "gateway_timeout": NotionAPIError,
}


def translate_error(exc: Exception) -> NoReturn:
    """Re-raise a notion_client exception as the matching NotionDBError subclass."""
    code = getattr(exc, "code", None)
    code_value = code.value if hasattr(code, "value") else code
    error_cls = _API_CODE_TO_ERROR.get(str(code_value), NotionAPIError)
    raise error_cls(str(exc)) from exc
