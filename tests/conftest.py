"""Shared pytest fixtures for docsync tests."""

import os
import pytest
from unittest.mock import MagicMock, patch

from docsync.config import DocSyncConfig
from docsync.confluence_client import ConfluenceClient, Page
from docsync.github_client import GitHubClient


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "test-token")
    monkeypatch.setenv("CONFLUENCE_USER", "test@example.com")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp-test-token")


@pytest.fixture
def base_config() -> DocSyncConfig:
    return DocSyncConfig(
        confluence_base_url="https://test.atlassian.net",
        space_key="TEST",
        root_page_id="111",
        docs_root="docs",
        include_globs=["**/*.md"],
        exclude_globs=[],
        batch_size=5,
        dry_run=False,
    )


@pytest.fixture
def mock_confluence(base_config) -> MagicMock:
    client = MagicMock(spec=ConfluenceClient)
    client.find_page.return_value = None
    client.find_page_by_property.return_value = None
    client.get_page_property.return_value = "file"
    client.list_all_pages_with_property.return_value = {}
    client.get_child_page_ids.return_value = []
    client.create_page.return_value = Page(id="999", title="Test", version=1, space_key="TEST")
    client.update_page.return_value = Page(id="999", title="Test", version=2, space_key="TEST")
    return client


@pytest.fixture
def mock_github() -> MagicMock:
    return MagicMock(spec=GitHubClient)


@pytest.fixture
def sample_markdown() -> str:
    return """# Hello World

This is a **test** document.

## Code Example

```python
def hello():
    print("Hello, World!")
```

## Table

| Col A | Col B |
|-------|-------|
| 1     | 2     |
"""
