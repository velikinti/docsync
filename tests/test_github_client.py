"""Tests for GitHubClient using mocked HTTP responses."""

import base64
import pytest
import httpx
import respx
import asyncio

from docsync.github_client import GitHubClient, ChangeType


@pytest.fixture
def client():
    return GitHubClient(token="ghp-test", batch_size=3)


class TestListChangedFiles:
    @respx.mock
    @pytest.mark.asyncio
    async def test_lists_added_and_modified_files(self, client):
        commit_data = {
            "files": [
                {"filename": "docs/intro.md", "status": "added"},
                {"filename": "docs/api.md", "status": "modified"},
                {"filename": "docs/old.md", "status": "removed"},
            ]
        }
        respx.get("https://api.github.com/repos/owner/repo/commits/abc123").mock(
            return_value=httpx.Response(200, json=commit_data)
        )
        files = await client.list_changed_files("owner", "repo", "abc123")
        assert len(files) == 3
        assert files[0].change_type == ChangeType.ADDED
        assert files[1].change_type == ChangeType.MODIFIED
        assert files[2].change_type == ChangeType.DELETED

    @respx.mock
    @pytest.mark.asyncio
    async def test_raises_on_api_error(self, client):
        respx.get("https://api.github.com/repos/owner/repo/commits/bad").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(RuntimeError, match="404"):
            await client.list_changed_files("owner", "repo", "bad")


class TestGetFileContent:
    @respx.mock
    @pytest.mark.asyncio
    async def test_decodes_base64_content(self, client):
        content = base64.b64encode(b"# Hello").decode()
        file_data = {"encoding": "base64", "content": content}
        respx.get("https://api.github.com/repos/owner/repo/contents/docs/hello.md").mock(
            return_value=httpx.Response(200, json=file_data)
        )
        result = await client.get_file_content("owner", "repo", "docs/hello.md", "main")
        assert result == b"# Hello"

    @respx.mock
    @pytest.mark.asyncio
    async def test_raises_file_not_found(self, client):
        respx.get("https://api.github.com/repos/owner/repo/contents/missing.md").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(FileNotFoundError):
            await client.get_file_content("owner", "repo", "missing.md", "main")


class TestFetchFilesBatch:
    @respx.mock
    @pytest.mark.asyncio
    async def test_fetches_multiple_files(self, client):
        def make_response(text: str):
            content = base64.b64encode(text.encode()).decode()
            return httpx.Response(200, json={"encoding": "base64", "content": content})

        respx.get("https://api.github.com/repos/o/r/contents/a.md").mock(return_value=make_response("# A"))
        respx.get("https://api.github.com/repos/o/r/contents/b.md").mock(return_value=make_response("# B"))

        results = await client.fetch_files_batch("o", "r", ["a.md", "b.md"], "main")
        assert results["a.md"] == b"# A"
        assert results["b.md"] == b"# B"

    @respx.mock
    @pytest.mark.asyncio
    async def test_skips_missing_files(self, client):
        respx.get("https://api.github.com/repos/o/r/contents/missing.md").mock(
            return_value=httpx.Response(404)
        )
        results = await client.fetch_files_batch("o", "r", ["missing.md"], "main")
        assert "missing.md" not in results
