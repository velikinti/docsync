"""Tests for TC-005 — archive_on_delete flag, page-not-found warning, RENAMED handling."""

from __future__ import annotations

import pytest
import structlog.testing
from unittest.mock import AsyncMock

from docsync.confluence_client import Page
from docsync.github_client import ChangedFile, ChangeType
from docsync.sync import SyncEngine, SyncStatus


@pytest.fixture
def engine(base_config, mock_confluence, mock_github):
    return SyncEngine(config=base_config, github=mock_github, confluence=mock_confluence)


def _setup_renamed(mock_github, old_path: str = "docs/old.md", new_path: str = "docs/new.md"):
    mock_github.list_changed_files = AsyncMock(
        return_value=[
            ChangedFile(path=new_path, change_type=ChangeType.RENAMED, previous_path=old_path)
        ]
    )
    mock_github.fetch_files_batch = AsyncMock(return_value={new_path: b"# New content"})


class TestArchiveOnDelete:
    def test_archive_on_delete_false_skips(self, base_config, mock_github, mock_confluence):
        cfg = base_config.model_copy(update={"archive_on_delete": False})
        engine = SyncEngine(config=cfg, github=mock_github, confluence=mock_confluence)

        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/old.md", change_type=ChangeType.DELETED)]
        )
        mock_github.fetch_files_batch = AsyncMock(return_value={})

        report = engine.run("owner", "repo", "abc123")

        assert report.results[0].status == SyncStatus.SKIPPED
        assert report.results[0].error == "archive_on_delete=false"
        mock_confluence.archive_page.assert_not_called()

    def test_archive_on_delete_false_logs_debug(self, base_config, mock_github, mock_confluence):
        cfg = base_config.model_copy(update={"archive_on_delete": False})
        engine = SyncEngine(config=cfg, github=mock_github, confluence=mock_confluence)

        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/old.md", change_type=ChangeType.DELETED)]
        )
        mock_github.fetch_files_batch = AsyncMock(return_value={})

        with structlog.testing.capture_logs() as logs:
            engine.run("owner", "repo", "abc123")

        assert any(l.get("event") == "archive_on_delete_disabled" for l in logs)

    def test_page_not_found_logs_warning(self, engine, mock_github, mock_confluence):
        mock_confluence.find_page_by_property.return_value = None
        mock_github.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/ghost.md", change_type=ChangeType.DELETED)]
        )
        mock_github.fetch_files_batch = AsyncMock(return_value={})

        with structlog.testing.capture_logs() as logs:
            report = engine.run("owner", "repo", "abc123")

        assert report.results[0].status == SyncStatus.SKIPPED
        warning_logs = [l for l in logs if l.get("log_level") == "warning"]
        assert any(l.get("event") == "page_not_found_for_delete" for l in warning_logs)


class TestRenamedFileHandling:
    def test_renamed_archives_previous_path(self, engine, mock_github, mock_confluence):
        _setup_renamed(mock_github)
        mock_confluence.find_page_by_property.return_value = "777"
        mock_confluence.get_page_property.return_value = "file"
        mock_confluence.find_page.return_value = None
        mock_confluence.create_page.return_value = Page("888", "New", 1, "TEST")

        report = engine.run("owner", "repo", "abc123")

        mock_confluence.archive_page.assert_called_once_with("777")
        assert report.results[0].status == SyncStatus.CREATED

    def test_renamed_upserts_new_path(self, engine, mock_github, mock_confluence):
        _setup_renamed(mock_github)
        mock_confluence.find_page_by_property.return_value = "777"
        mock_confluence.get_page_property.return_value = "file"
        mock_confluence.find_page.return_value = None
        mock_confluence.create_page.return_value = Page("888", "New", 1, "TEST")

        report = engine.run("owner", "repo", "abc123")

        file_calls = [
            c for c in mock_confluence.create_page.call_args_list
            if c.kwargs.get("path_type") == "file"
        ]
        assert len(file_calls) == 1
        assert file_calls[0].kwargs["source_path"] == "docs/new.md"
        assert report.results[0].page_id == "888"

    def test_renamed_archive_failure_does_not_block_upsert(
        self, engine, mock_github, mock_confluence
    ):
        _setup_renamed(mock_github)
        mock_confluence.find_page_by_property.return_value = "777"
        mock_confluence.get_page_property.return_value = "file"
        mock_confluence.archive_page.side_effect = RuntimeError("Confluence API error")
        mock_confluence.find_page.return_value = None
        mock_confluence.create_page.return_value = Page("888", "New", 1, "TEST")

        with structlog.testing.capture_logs() as logs:
            report = engine.run("owner", "repo", "abc123")

        assert report.results[0].status == SyncStatus.CREATED
        assert any(l.get("event") == "rename_archive_failed" for l in logs)

    def test_renamed_dry_run_skips_archive_and_upsert(
        self, base_config, mock_github, mock_confluence
    ):
        cfg = base_config.model_copy(update={"dry_run": True})
        engine = SyncEngine(config=cfg, github=mock_github, confluence=mock_confluence)
        _setup_renamed(mock_github)

        report = engine.run("owner", "repo", "abc123")

        assert report.results[0].status == SyncStatus.SKIPPED
        mock_confluence.archive_page.assert_not_called()
        mock_confluence.create_page.assert_not_called()

    def test_renamed_no_previous_path_skips_archive(self, engine, mock_github, mock_confluence):
        mock_github.list_changed_files = AsyncMock(
            return_value=[
                ChangedFile(
                    path="docs/new.md", change_type=ChangeType.RENAMED, previous_path=None
                )
            ]
        )
        mock_github.fetch_files_batch = AsyncMock(return_value={"docs/new.md": b"# New content"})
        mock_confluence.find_page.return_value = None
        mock_confluence.create_page.return_value = Page("888", "New", 1, "TEST")

        report = engine.run("owner", "repo", "abc123")

        mock_confluence.archive_page.assert_not_called()
        assert report.results[0].status == SyncStatus.CREATED
