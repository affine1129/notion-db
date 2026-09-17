from __future__ import annotations

import httpx
import pytest

from notion_db.exceptions import (
    NotionAPIError,
    NotionAuthError,
    NotionDBError,
    NotionNotFoundError,
    NotionRateLimitError,
    NotionValidationError,
    translate_error,
)
from notion_db.http import NotionHTTPError


def _api_error(code: str) -> NotionHTTPError:
    return NotionHTTPError(
        code=code,
        status=400,
        message="boom",
        headers=httpx.Headers(),
        raw_body_text="{}",
    )


@pytest.mark.parametrize(
    ("code", "expected_cls"),
    [
        ("unauthorized", NotionAuthError),
        ("restricted_resource", NotionAuthError),
        ("object_not_found", NotionNotFoundError),
        ("rate_limited", NotionRateLimitError),
        ("validation_error", NotionValidationError),
        ("internal_server_error", NotionAPIError),
        ("some_future_unknown_code", NotionAPIError),
    ],
)
def test_translate_error_maps_codes(code, expected_cls):
    with pytest.raises(expected_cls) as excinfo:
        translate_error(_api_error(code))
    assert isinstance(excinfo.value, NotionDBError)
    assert excinfo.value.__cause__ is not None
