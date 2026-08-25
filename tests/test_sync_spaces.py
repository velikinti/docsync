"""Tests for SyncEngine multi-space routing — pre-flight, filtering, by_space()."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from docsync.config import DocSyncConfig
from docsync.confluence_client import ConfluenceClient, Page, SpaceAccessResult
from docsync.github_client import ChangedFile, ChangeType, GitHubClient
from docsync.space_router import SpaceRouter
from docsync.sync import SyncEngine, SyncReport, SyncResult, SyncStatus


SPACE_OK = SpaceAccessResult(space_key="DOCS", exists=True, can_read=True, can_write=True)
SPACE_ENG_OK = SpaceAccessResult(space_key="ENG", exists=True, can_read=True, can_write=True)
SPACE_FAIL = SpaceAccessResult(
    space_key="DOCS", exists=False, can_read=False, can_write=False, error="Space 'DOCS' not found"
)


@pytest.fixture
def multi_config():
    return DocSyncConfig(
        confluence_base_url="https://test.atlassian.net",
        space_mappings={"docs/": "DOCS", "engineering/": "ENG"},
        root_page_id="111",
        docs_root="docs",
        include_globs=["**/*.md"],
        exclude_globs=[],
        batch_size=5,
        dry_run=False,
    )


@pytest.fixture
def mock_cf():
    client = MagicMock(spec=ConfluenceClient)
    client.find_page.return_value = None
    client.create_page.return_value = Page(id="999", title="Test", version=1, space_key="DOCS")
    client.check_space_access.return_value = SPACE_OK
    return client


@pytest.fixture
def mock_gh():
    return MagicMock(spec=GitHubClient)


def _engine(config, mock_gh, mock_cf, mappings):
    router = SpaceRouter(mappings)
    return SyncEngine(config=config, github=mock_gh, confluence=mock_cf, space_router=router)


class TestPreflightAbort:
    def test_raises_when_space_not_found(self, multi_config, mock_gh, mock_cf):
        mock_cf.check_space_access.return_value = SPACE_FAIL
        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)

        with pytest.raises(RuntimeError, match="Pre-flight failed"):
            engine.run("owner", "repo", "abc123", active_spaces=["DOCS"])

        mock_gh.list_changed_files.assert_not_called()

    def test_no_files_processed_on_preflight_failure(self, multi_config, mock_gh, mock_cf):
        mock_cf.check_space_access.return_value = SPACE_FAIL
        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)

        try:
            engine.run("owner", "repo", "abc123", active_spaces=["DOCS"])
        except RuntimeError:
            pass

        mock_cf.create_page.assert_not_called()
        mock_cf.update_page.assert_not_called()


class TestPreflightContinueOnError:
    def test_failing_space_dropped_others_continue(self, multi_config, mock_gh, mock_cf):
        docs_fail = SpaceAccessResult(
            space_key="DOCS", exists=False, can_read=False, can_write=False, error="not found"
        )
        mock_cf.check_space_access.side_effect = [docs_fail, SPACE_ENG_OK]

        mock_gh.list_changed_files = AsyncMock(
            return_value=[
                ChangedFile(path="engineering/setup.md", change_type=ChangeType.ADDED),
            ]
        )
        mock_gh.fetch_files_batch = AsyncMock(
            return_value={"engineering/setup.md": b"# Setup"}
        )
        mock_cf.create_page.return_value = Page("888", "Setup", 1, "ENG")

        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)
        report = engine.run(
            "owner", "repo", "abc123",
            active_spaces=["DOCS", "ENG"],
            continue_on_error=True,
        )

        synced = [r for r in report.results if r.status == SyncStatus.CREATED]
        assert len(synced) == 1
        assert synced[0].space_key == "ENG"

    def test_all_spaces_fail_returns_empty_report(self, multi_config, mock_gh, mock_cf):
        docs_fail = SpaceAccessResult(
            space_key="DOCS", exists=False, can_read=False, can_write=False, error="not found"
        )
        mock_cf.check_space_access.return_value = docs_fail
        mock_gh.list_changed_files = AsyncMock(return_value=[])
        mock_gh.fetch_files_batch = AsyncMock(return_value={})

        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)
        report = engine.run(
            "owner", "repo", "abc123",
            active_spaces=["DOCS"],
            continue_on_error=True,
        )

        assert report.results == []


class TestFileRouting:
    def test_file_mapped_to_active_space_is_synced(self, multi_config, mock_gh, mock_cf):
        mock_gh.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/intro.md", change_type=ChangeType.ADDED)]
        )
        mock_gh.fetch_files_batch = AsyncMock(
            return_value={"docs/intro.md": b"# Intro"}
        )
        mock_cf.create_page.return_value = Page("999", "Intro", 1, "DOCS")

        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)
        report = engine.run("owner", "repo", "sha", active_spaces=["DOCS"])

        assert report.results[0].status == SyncStatus.CREATED
        assert report.results[0].space_key == "DOCS"
        _, kwargs = mock_cf.create_page.call_args
        assert kwargs.get("space_key") == "DOCS"

    def test_file_mapped_to_inactive_space_is_skipped(self, multi_config, mock_gh, mock_cf):
        mock_gh.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="engineering/setup.md", change_type=ChangeType.ADDED)]
        )
        mock_gh.fetch_files_batch = AsyncMock(return_value={})

        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)
        report = engine.run("owner", "repo", "sha", active_spaces=["DOCS"])

        assert report.results[0].status == SyncStatus.SKIPPED
        assert "space not in --spaces filter" in report.results[0].error

    def test_unmapped_file_is_skipped_with_warning(self, multi_config, mock_gh, mock_cf):
        mock_gh.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="other/readme.md", change_type=ChangeType.ADDED)]
        )
        mock_gh.fetch_files_batch = AsyncMock(return_value={})

        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)
        report = engine.run("owner", "repo", "sha", active_spaces=["DOCS"])

        assert report.results[0].status == SyncStatus.SKIPPED
        assert report.results[0].error == "no space_mapping for path"

    def test_mixed_files_routed_correctly(self, multi_config, mock_gh, mock_cf):
        mock_cf.check_space_access.side_effect = [SPACE_OK, SPACE_ENG_OK]
        mock_gh.list_changed_files = AsyncMock(
            return_value=[
                ChangedFile(path="docs/intro.md", change_type=ChangeType.ADDED),
                ChangedFile(path="engineering/setup.md", change_type=ChangeType.ADDED),
                ChangedFile(path="other/readme.md", change_type=ChangeType.ADDED),
            ]
        )
        mock_gh.fetch_files_batch = AsyncMock(
            return_value={
                "docs/intro.md": b"# Intro",
                "engineering/setup.md": b"# Setup",
            }
        )
        mock_cf.create_page.side_effect = [
            Page("1", "Intro", 1, "DOCS"),
            Page("2", "Setup", 1, "ENG"),
        ]

        engine = _engine(multi_config, mock_gh, mock_cf, multi_config.space_mappings)
        report = engine.run(
            "owner", "repo", "sha", active_spaces=["DOCS", "ENG"]
        )

        statuses = {r.path: r.status for r in report.results}
        assert statuses["docs/intro.md"] == SyncStatus.CREATED
        assert statuses["engineering/setup.md"] == SyncStatus.CREATED
        assert statuses["other/readme.md"] == SyncStatus.SKIPPED


class TestLegacySingleSpaceMode:
    def test_legacy_engine_works_without_router(self, base_config, mock_gh, mock_cf):
        mock_gh.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/intro.md", change_type=ChangeType.ADDED)]
        )
        mock_gh.fetch_files_batch = AsyncMock(
            return_value={"docs/intro.md": b"# Intro"}
        )
        mock_cf.create_page.return_value = Page("999", "Intro", 1, "TEST")

        engine = SyncEngine(config=base_config, github=mock_gh, confluence=mock_cf)
        report = engine.run("owner", "repo", "abc123")

        assert report.results[0].status == SyncStatus.CREATED
        assert report.results[0].space_key == "TEST"
        mock_cf.check_space_access.assert_not_called()

    def test_legacy_find_page_uses_space_key(self, base_config, mock_gh, mock_cf):
        mock_gh.list_changed_files = AsyncMock(
            return_value=[ChangedFile(path="docs/intro.md", change_type=ChangeType.MODIFIED)]
        )
        mock_gh.fetch_files_batch = AsyncMock(
            return_value={"docs/intro.md": b"# Intro updated"}
        )
        mock_cf.find_page.return_value = Page("123", "Intro", 1, "TEST")
        mock_cf.update_page.return_value = Page("123", "Intro", 2, "TEST")

        engine = SyncEngine(config=base_config, github=mock_gh, confluence=mock_cf)
        engine.run("owner", "repo", "abc123")

        mock_cf.find_page.assert_called_once_with("TEST", "docs/intro.md")


class TestSyncReportBySpace:
    def test_by_space_groups_correctly(self):
        report = SyncReport()
        report.results = [
            SyncResult(path="docs/a.md", status=SyncStatus.CREATED, space_key="DOCS"),
            SyncResult(path="docs/b.md", status=SyncStatus.UPDATED, space_key="DOCS"),
            SyncResult(path="eng/c.md", status=SyncStatus.CREATED, space_key="ENG"),
            SyncResult(path="other/d.md", status=SyncStatus.SKIPPED),
        ]
        grouped = report.by_space()

        assert len(grouped["DOCS"]) == 2
        assert len(grouped["ENG"]) == 1
        assert len(grouped[""]) == 1

    def test_by_space_empty_report(self):
        assert SyncReport().by_space() == {}

    def test_by_space_all_same_space(self):
        report = SyncReport()
        report.results = [
            SyncResult(path="docs/a.md", status=SyncStatus.CREATED, space_key="DOCS"),
            SyncResult(path="docs/b.md", status=SyncStatus.CREATED, space_key="DOCS"),
        ]
        grouped = report.by_space()
        assert list(grouped.keys()) == ["DOCS"]
        assert len(grouped["DOCS"]) == 2
