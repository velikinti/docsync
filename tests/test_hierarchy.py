"""Tests for HierarchyManager — TC-004 nested directory hierarchy."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from docsync.confluence_client import ConfluenceClient, Page
from docsync.hierarchy import HierarchyManager


BASE_URL = "https://test.atlassian.net"


@pytest.fixture
def mock_cf():
    """Return a MagicMock ConfluenceClient with sensible defaults."""
    cf = MagicMock(spec=ConfluenceClient)
    cf.list_all_pages_with_property.return_value = {}
    cf.find_page_by_property.return_value = None
    cf.create_page.return_value = Page(id="new-page-id", title="seg", version=1, space_key="TEST")
    cf.get_child_page_ids.return_value = []
    cf.archive_page.return_value = None
    return cf


@pytest.fixture
def hm(mock_cf):
    return HierarchyManager(
        confluence=mock_cf,
        space_key="TEST",
        root_page_id="root-id",
        dry_run=False,
        max_archive_depth=50,
        batch_size=5,
    )


class TestPrefetchPageCache:
    def test_populates_cache_from_confluence(self, hm, mock_cf):
        mock_cf.list_all_pages_with_property.return_value = {
            "docs/api": "pg-api",
            "docs/api/overview.md": "pg-overview",
        }
        hm.prefetch_page_cache()
        assert hm._page_id_cache["docs/api"] == "pg-api"
        assert hm._page_id_cache["docs/api/overview.md"] == "pg-overview"

    def test_empty_space_sets_empty_cache(self, hm, mock_cf):
        mock_cf.list_all_pages_with_property.return_value = {}
        hm.prefetch_page_cache()
        assert hm._page_id_cache == {}


class TestResolveParentIdSingleLevel:
    def test_top_level_file_returns_root(self, hm):
        parent = asyncio.run(hm.resolve_parent_id("readme.md"))
        assert parent == "root-id"

    def test_one_level_deep_creates_parent(self, hm, mock_cf):
        mock_cf.find_page_by_property.return_value = None
        mock_cf.create_page.return_value = Page(
            id="docs-page-id", title="docs", version=1, space_key="TEST"
        )
        parent = asyncio.run(hm.resolve_parent_id("docs/overview.md"))
        assert parent == "docs-page-id"
        mock_cf.create_page.assert_called_once_with(
            space_key="TEST",
            parent_id="root-id",
            title="docs",
            body="",
            source_path="docs",
            path_type="directory",
        )

    def test_existing_parent_not_recreated(self, hm, mock_cf):
        mock_cf.find_page_by_property.return_value = "existing-docs-id"
        parent = asyncio.run(hm.resolve_parent_id("docs/overview.md"))
        assert parent == "existing-docs-id"
        mock_cf.create_page.assert_not_called()


class TestResolveParentIdMultiLevel:
    def test_three_level_chain_creates_intermediate_pages(self, hm, mock_cf):
        call_count = [0]
        page_ids = ["docs-id", "api-id", "v2-id"]

        def side_effect(**kwargs):
            pid = page_ids[call_count[0]]
            call_count[0] += 1
            return Page(id=pid, title=kwargs["title"], version=1, space_key="TEST")

        mock_cf.find_page_by_property.return_value = None
        mock_cf.create_page.side_effect = side_effect

        parent = asyncio.run(hm.resolve_parent_id("docs/api/v2/auth.md"))
        assert parent == "v2-id"
        assert mock_cf.create_page.call_count == 3

    def test_second_call_uses_cache(self, hm, mock_cf):
        mock_cf.find_page_by_property.return_value = None
        mock_cf.create_page.return_value = Page(
            id="docs-id", title="docs", version=1, space_key="TEST"
        )

        asyncio.run(hm.resolve_parent_id("docs/overview.md"))
        # Second call — cache hit, no new create
        mock_cf.create_page.reset_mock()
        asyncio.run(hm.resolve_parent_id("docs/intro.md"))
        mock_cf.create_page.assert_not_called()


class TestConcurrentDirectoryCreation:
    def test_lock_prevents_duplicate_page_creation(self, mock_cf):
        """Two concurrent resolve_parent_id calls for same dir must create page only once."""
        create_count = [0]

        def slow_find(space_key, property_key, property_value):
            return None  # always miss

        def counting_create(**kwargs):
            create_count[0] += 1
            return Page(id="docs-id", title="docs", version=1, space_key="TEST")

        mock_cf.find_page_by_property.side_effect = slow_find
        mock_cf.create_page.side_effect = counting_create
        mock_cf.list_all_pages_with_property.return_value = {}

        hm = HierarchyManager(
            confluence=mock_cf,
            space_key="TEST",
            root_page_id="root-id",
        )

        async def run():
            results = await asyncio.gather(
                hm.resolve_parent_id("docs/a.md"),
                hm.resolve_parent_id("docs/b.md"),
            )
            return results

        results = asyncio.run(run())

        # Both should return the same parent id
        assert results[0] == results[1] == "docs-id"
        # Page should only be created once despite two concurrent calls
        assert create_count[0] == 1


class TestDryRun:
    def test_dry_run_returns_synthetic_id(self, mock_cf):
        hm = HierarchyManager(
            confluence=mock_cf,
            space_key="TEST",
            root_page_id="root-id",
            dry_run=True,
        )
        parent = asyncio.run(hm.resolve_parent_id("docs/overview.md"))
        assert parent.startswith("dry-run-")
        assert len(parent) == len("dry-run-") + 8

    def test_dry_run_deterministic_for_same_path(self, mock_cf):
        hm = HierarchyManager(
            confluence=mock_cf,
            space_key="TEST",
            root_page_id="root-id",
            dry_run=True,
        )
        p1 = asyncio.run(hm.resolve_parent_id("docs/overview.md"))
        hm._page_id_cache.clear()
        p2 = asyncio.run(hm.resolve_parent_id("docs/overview.md"))
        assert p1 == p2

    def test_dry_run_does_not_call_confluence_write(self, mock_cf):
        hm = HierarchyManager(
            confluence=mock_cf,
            space_key="TEST",
            root_page_id="root-id",
            dry_run=True,
        )
        asyncio.run(hm.resolve_parent_id("docs/api/auth.md"))
        mock_cf.create_page.assert_not_called()


class TestArchiveDirectory:
    def test_archives_root_and_descendants(self, hm, mock_cf):
        mock_cf.find_page_by_property.return_value = "dir-page-id"
        mock_cf.get_child_page_ids.side_effect = lambda pid: (
            ["child-1", "child-2"] if pid == "dir-page-id" else []
        )

        archived = asyncio.run(hm.archive_directory("docs/api"))
        assert "dir-page-id" in archived
        assert "child-1" in archived
        assert "child-2" in archived
        assert mock_cf.archive_page.call_count == 3

    def test_no_page_found_returns_empty(self, hm, mock_cf):
        mock_cf.find_page_by_property.return_value = None
        archived = asyncio.run(hm.archive_directory("docs/api"))
        assert archived == []
        mock_cf.archive_page.assert_not_called()

    def test_dry_run_does_not_call_archive(self, mock_cf):
        hm = HierarchyManager(
            confluence=mock_cf,
            space_key="TEST",
            root_page_id="root-id",
            dry_run=True,
        )
        mock_cf.find_page_by_property.return_value = "dir-page-id"
        mock_cf.get_child_page_ids.return_value = []

        archived = asyncio.run(hm.archive_directory("docs/api"))
        assert archived == ["dir-page-id"]
        mock_cf.archive_page.assert_not_called()


class TestMaxArchiveDepth:
    def test_depth_limit_stops_recursion(self, mock_cf):
        hm = HierarchyManager(
            confluence=mock_cf,
            space_key="TEST",
            root_page_id="root-id",
            max_archive_depth=2,
        )
        # Simulate deep tree: page->child->grandchild->great-grandchild
        mock_cf.get_child_page_ids.side_effect = lambda pid: [f"{pid}-child"]

        result = asyncio.run(hm._collect_descendants("page-0"))
        # At depth 0: get children of page-0 -> [page-0-child]
        # At depth 1: get children of page-0-child -> [page-0-child-child]
        # At depth 2: max_archive_depth reached -> stop
        assert len(result) == 2
