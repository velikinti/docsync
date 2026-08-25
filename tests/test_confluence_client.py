"""Tests for ConfluenceClient using mocked HTTP responses."""

import json
import pytest
import httpx
import respx

from docsync.confluence_client import ConfluenceClient, Page, DOCSYNC_PROPERTY_KEY


BASE_URL = "https://test.atlassian.net"


@pytest.fixture
def client():
    return ConfluenceClient(base_url=BASE_URL, user="user@test.com", token="secret")


class TestFindPage:
    @respx.mock
    def test_finds_page_by_source_path(self, client):
        page_data = {
            "results": [
                {
                    "id": "123",
                    "title": "Overview",
                    "version": {"number": 3},
                    "space": {"key": "TEST"},
                    "metadata": {
                        "properties": {
                            "results": [
                                {"key": DOCSYNC_PROPERTY_KEY, "value": "docs/overview.md"}
                            ]
                        }
                    },
                }
            ]
        }
        respx.get(f"{BASE_URL}/wiki/rest/api/content").mock(
            return_value=httpx.Response(200, json=page_data)
        )
        page = client.find_page("TEST", "docs/overview.md")
        assert page is not None
        assert page.id == "123"
        assert page.version == 3

    @respx.mock
    def test_returns_none_when_not_found(self, client):
        respx.get(f"{BASE_URL}/wiki/rest/api/content").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        page = client.find_page("TEST", "docs/missing.md")
        assert page is None

    @respx.mock
    def test_raises_on_api_error(self, client):
        respx.get(f"{BASE_URL}/wiki/rest/api/content").mock(
            return_value=httpx.Response(500, text="Server Error")
        )
        with pytest.raises(RuntimeError, match="500"):
            client.find_page("TEST", "docs/overview.md")


class TestCreatePage:
    @respx.mock
    def test_creates_page_successfully(self, client):
        response_data = {
            "id": "456",
            "title": "New Page",
            "version": {"number": 1},
            "space": {"key": "TEST"},
        }
        respx.post(f"{BASE_URL}/wiki/rest/api/content").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        page = client.create_page("TEST", "111", "New Page", "<p>body</p>", "docs/new.md")
        assert page.id == "456"
        assert page.title == "New Page"
        assert page.version == 1


class TestUpdatePage:
    @respx.mock
    def test_updates_page_successfully(self, client):
        response_data = {
            "id": "123",
            "title": "Updated Page",
            "version": {"number": 4},
            "space": {"key": "TEST"},
        }
        respx.put(f"{BASE_URL}/wiki/rest/api/content/123").mock(
            return_value=httpx.Response(200, json=response_data)
        )
        page = client.update_page("123", 3, "Updated Page", "<p>new body</p>")
        assert page.version == 4


class TestArchivePage:
    @respx.mock
    def test_archives_page(self, client):
        respx.delete(f"{BASE_URL}/wiki/rest/api/content/123").mock(
            return_value=httpx.Response(204)
        )
        client.archive_page("123")  # should not raise

    @respx.mock
    def test_archive_idempotent_on_404(self, client):
        respx.delete(f"{BASE_URL}/wiki/rest/api/content/missing").mock(
            return_value=httpx.Response(404)
        )
        client.archive_page("missing")  # should not raise
