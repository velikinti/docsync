"""Tests for SyncEngine — happy path, dry-run, deletion, partial failure."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from docsync.confluence_client import ConfluenceClient, Page
from docsync.github_client import ChangedFile, ChangeType, GitHubClient
from docsync.sync import SyncEngine, SyncStatus, SyncReport


@pytest.fixture
def engine(base_config, mock_confluence, mock_github):
    return SyncEngine(config=base_config, github=mock_github, confluence=mock_confluence)


class TestSyncEngineHappyPath:
    def test_creates_new_page_for_added_file(self, engine, mock_github, mock_confluence):
        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/intro.md", change_type=ChangeType.ADDED)]
        )
        mock_github.fetch_files_batch = AsyncMock(
            return_value={"docs/intro.md": b"# Intro\nContent here."}
        )
        mock_confluence.find_page.return_value = None
        mock_confluence.create_page.return_value = Page("999", "Intro", 1, "TEST")

        report = engine.run("owner", "repo", "abc123")
        assert report.results[0].status == SyncStatus.CREATED
        assert report.results[0].page_id == "999"
        # create_page is called at least once for the file (may also create intermediate dir pages)
        assert mock_confluence.create_page.called
        # Verify the file page was created with path_type="file"
        file_calls = [
            c for c in mock_confluence.create_page.call_args_list
            if c.kwargs.get("path_type") == "file"
        ]
        assert len(file_calls) == 1

    def test_updates_existing_page(self, engine, mock_github, mock_confluence):
        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/guide.md", change_type=ChangeType.MODIFIED)]
        )
        mock_github.fetch_files_batch = AsyncMock(
            return_value={"docs/guide.md": b"# Guide\nUpdated content."}
        )
        mock_confluence.find_page.return_value = Page("123", "Guide", 2, "TEST")
        mock_confluence.update_page.return_value = Page("123", "Guide", 3, "TEST")

        report = engine.run("owner", "repo", "abc123")
        assert report.results[0].status == SyncStatus.UPDATED
        mock_confluence.update_page.assert_called_once()

    def test_archives_deleted_file(self, engine, mock_github, mock_confluence):
        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/old.md", change_type=ChangeType.DELETED)]
        )
        mock_github.fetch_files_batch = AsyncMock(return_value={})
        mock_confluence.find_page_by_property.return_value = "777"
        mock_confluence.get_page_property.return_value = "file"

        report = engine.run("owner", "repo", "abc123")
        assert report.results[0].status == SyncStatus.ARCHIVED
        mock_confluence.archive_page.assert_called_once_with("777")

    def test_skips_deleted_file_not_in_confluence(self, engine, mock_github, mock_confluence):
        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/ghost.md", change_type=ChangeType.DELETED)]
        )
        mock_github.fetch_files_batch = AsyncMock(return_value={})
        mock_confluence.find_page_by_property.return_value = None

        report = engine.run("owner", "repo", "abc123")
        assert report.results[0].status == SyncStatus.SKIPPED


class TestDryRun:
    def test_dry_run_skips_all_writes(self, base_config, mock_github, mock_confluence):
        cfg = base_config.model_copy(update={"dry_run": True})
        engine = SyncEngine(config=cfg, github=mock_github, confluence=mock_confluence)

        mock_github.list_changed_files = AsyncMock(
            return_value=[
                ChangedFile(path="docs/intro.md", change_type=ChangeType.ADDED),
                ChangedFile(path="docs/old.md", change_type=ChangeType.DELETED),
            ]
        )
        mock_github.fetch_files_batch = AsyncMock(
            return_value={"docs/intro.md": b"# Intro"}
        )

        report = engine.run("owner", "repo", "abc123")
        assert all(r.status == SyncStatus.SKIPPED for r in report.results)
        mock_confluence.create_page.assert_not_called()
        mock_confluence.archive_page.assert_not_called()


class TestGlobFiltering:
    def test_excluded_files_are_skipped(self, base_config, mock_github, mock_confluence):
        cfg = base_config.model_copy(update={"exclude_globs": ["docs/drafts/**"]})
        engine = SyncEngine(config=cfg, github=mock_github, confluence=mock_confluence)

        mock_github.list_changed_files = AsyncMock(
            return_value=[
                ChangedFile(path="docs/drafts/wip.md", change_type=ChangeType.ADDED),
                ChangedFile(path="docs/intro.md", change_type=ChangeType.ADDED),
            ]
        )
        mock_github.fetch_files_batch = AsyncMock(
            return_value={"docs/intro.md": b"# Intro"}
        )
        mock_confluence.find_page.return_value = None
        mock_confluence.create_page.return_value = Page("1", "Intro", 1, "TEST")

        report = engine.run("owner", "repo", "abc123")
        paths = [r.path for r in report.results]
        assert "docs/drafts/wip.md" not in paths
        assert "docs/intro.md" in paths


class TestPartialFailure:
    def test_failure_on_one_file_does_not_stop_others(self, engine, mock_github, mock_confluence):
        mock_github.list_changed_files = AsyncMock(
            return_value=[
                ChangedFile(path="docs/a.md", change_type=ChangeType.ADDED),
                ChangedFile(path="docs/b.md", change_type=ChangeType.ADDED),
            ]
        )
        mock_github.fetch_files_batch = AsyncMock(
            return_value={
                "docs/a.md": b"# A",
                "docs/b.md": b"# B",
            }
        )
        mock_confluence.find_page.return_value = None
        # create_page is called: 1st for intermediate "docs" dir, 2nd for a.md (fails),
        # 3rd skipped (cache hit for "docs"), 4th for b.md
        mock_confluence.create_page.side_effect = [
            Page("dir-docs", "docs", 1, "TEST"),   # intermediate dir page
            RuntimeError("API error on a.md"),      # a.md fails
            Page("2", "B", 1, "TEST"),              # b.md succeeds
        ]

        report = engine.run("owner", "repo", "abc123")
        statuses = {r.path: r.status for r in report.results}
        assert statuses["docs/a.md"] == SyncStatus.FAILED
        assert statuses["docs/b.md"] == SyncStatus.CREATED
        assert report.failure_count == 1
        assert report.success_count == 1


class TestSyncReport:
    def test_counts_are_correct(self):
        report = SyncReport()
        report.results = [
            MagicMock(status=SyncStatus.CREATED),
            MagicMock(status=SyncStatus.UPDATED),
            MagicMock(status=SyncStatus.ARCHIVED),
            MagicMock(status=SyncStatus.SKIPPED),
            MagicMock(status=SyncStatus.FAILED),
        ]
        assert report.success_count == 3
        assert report.skip_count == 1
        assert report.failure_count == 1
