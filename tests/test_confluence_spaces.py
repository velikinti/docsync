"""Tests for ConfluenceClient.check_space_access."""

from __future__ import annotations

import pytest
import httpx
from unittest.mock import MagicMock, patch

from docsync.confluence_client import ConfluenceClient, SpaceAccessResult


def _make_client(responses: list) -> ConfluenceClient:
    """Return a ConfluenceClient whose _client() returns sequential mock contexts."""
    cf = ConfluenceClient("https://test.atlassian.net", "user@test.com", "token")

    mocks = []
    for resp in responses:
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        ctx.get.return_value = resp
        mocks.append(ctx)

    cf._client = MagicMock(side_effect=mocks)
    return cf


def _ok_resp(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def _error_resp(status_code: int) -> MagicMock:
    mock_request = MagicMock()
    raw = MagicMock()
    raw.status_code = status_code
    raw.text = "Error"
    exc = httpx.HTTPStatusError("HTTP error", request=mock_request, response=raw)
    resp = MagicMock()
    resp.raise_for_status = MagicMock(side_effect=exc)
    return resp


class TestCheckSpaceAccessFound:
    def test_space_found_and_writable(self):
        spaces_resp = _ok_resp({"results": [{"id": "space123"}]})
        perms_resp = _ok_resp({
            "results": [{"operation": {"operation": "create", "targetType": "page"}}]
        })
        cf = _make_client([spaces_resp, perms_resp])

        result = cf.check_space_access("DOCS")

        assert result.space_key == "DOCS"
        assert result.exists is True
        assert result.can_read is True
        assert result.can_write is True
        assert result.error is None

    def test_space_found_but_read_only(self):
        spaces_resp = _ok_resp({"results": [{"id": "space123"}]})
        perms_resp = _ok_resp({"results": [{"operation": {"operation": "read"}}]})
        cf = _make_client([spaces_resp, perms_resp])

        result = cf.check_space_access("DOCS")

        assert result.exists is True
        assert result.can_read is True
        assert result.can_write is False

    def test_space_found_but_no_permissions_entries(self):
        spaces_resp = _ok_resp({"results": [{"id": "space123"}]})
        perms_resp = _ok_resp({"results": []})
        cf = _make_client([spaces_resp, perms_resp])

        result = cf.check_space_access("DOCS")

        assert result.exists is True
        assert result.can_write is False


class TestCheckSpaceAccessNotFound:
    def test_space_not_found_empty_results(self):
        spaces_resp = _ok_resp({"results": []})
        cf = _make_client([spaces_resp])

        result = cf.check_space_access("BADKEY")

        assert result.space_key == "BADKEY"
        assert result.exists is False
        assert result.can_read is False
        assert result.can_write is False
        assert "BADKEY" in result.error
        assert "not found" in result.error

    def test_spaces_endpoint_returns_403(self):
        error_resp = _error_resp(403)
        cf = _make_client([error_resp])

        result = cf.check_space_access("PRIVATE")

        assert result.exists is False
        assert result.can_write is False
        assert "403" in result.error
        assert "PRIVATE" in result.error

    def test_spaces_endpoint_returns_404(self):
        error_resp = _error_resp(404)
        cf = _make_client([error_resp])

        result = cf.check_space_access("MISSING")

        assert result.exists is False
        assert "404" in result.error


class TestCheckSpaceAccessPermissionsError:
    def test_permissions_endpoint_returns_403(self):
        spaces_resp = _ok_resp({"results": [{"id": "space123"}]})
        perms_error = _error_resp(403)
        cf = _make_client([spaces_resp, perms_error])

        result = cf.check_space_access("DOCS")

        assert result.exists is True
        assert result.can_read is True
        assert result.can_write is False
        assert "403" in result.error
        assert "DOCS" in result.error
