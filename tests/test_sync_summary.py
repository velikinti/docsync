"""Tests for SyncReport summary counters and CLI summary output (US-003)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from docsync.sync import SyncReport, SyncResult, SyncStatus


# ---------------------------------------------------------------------------
# Unit tests — SyncReport properties
# ---------------------------------------------------------------------------


def _make_report(*statuses: SyncStatus) -> SyncReport:
    results = [SyncResult(path=f"docs/file{i}.md", status=s) for i, s in enumerate(statuses)]
    report = SyncReport(results=results, elapsed_seconds=1.2345)
    return report


def test_created_count():
    report = _make_report(SyncStatus.CREATED, SyncStatus.CREATED, SyncStatus.UPDATED)
    assert report.created_count == 2


def test_updated_count():
    report = _make_report(SyncStatus.UPDATED, SyncStatus.CREATED)
    assert report.updated_count == 1


def test_archived_count():
    report = _make_report(SyncStatus.ARCHIVED, SyncStatus.ARCHIVED)
    assert report.archived_count == 2


def test_skipped_count():
    report = _make_report(SyncStatus.SKIPPED, SyncStatus.CREATED)
    assert report.skipped_count == 1


def test_error_count():
    report = _make_report(SyncStatus.FAILED, SyncStatus.FAILED, SyncStatus.CREATED)
    assert report.error_count == 2


def test_all_zeros():
    report = SyncReport()
    assert report.created_count == 0
    assert report.updated_count == 0
    assert report.archived_count == 0
    assert report.skipped_count == 0
    assert report.error_count == 0


def test_backward_compat_skip_count():
    report = _make_report(SyncStatus.SKIPPED, SyncStatus.SKIPPED)
    assert report.skip_count == report.skipped_count == 2


def test_backward_compat_failure_count():
    report = _make_report(SyncStatus.FAILED)
    assert report.failure_count == report.error_count == 1


def test_success_count_includes_created_updated_archived():
    report = _make_report(
        SyncStatus.CREATED, SyncStatus.UPDATED, SyncStatus.ARCHIVED,
        SyncStatus.SKIPPED, SyncStatus.FAILED
    )
    assert report.success_count == 3


def test_summary_dict_keys():
    report = _make_report(SyncStatus.CREATED, SyncStatus.SKIPPED)
    d = report.summary_dict()
    assert set(d.keys()) == {"created", "updated", "archived", "skipped", "errors", "elapsed_seconds"}


def test_summary_dict_values():
    report = _make_report(
        SyncStatus.CREATED, SyncStatus.UPDATED, SyncStatus.ARCHIVED,
        SyncStatus.SKIPPED, SyncStatus.FAILED
    )
    report.elapsed_seconds = 2.5678
    d = report.summary_dict()
    assert d["created"] == 1
    assert d["updated"] == 1
    assert d["archived"] == 1
    assert d["skipped"] == 1
    assert d["errors"] == 1
    assert d["elapsed_seconds"] == 2.57


def test_summary_dict_elapsed_rounded_two_dp():
    report = SyncReport(elapsed_seconds=3.99999)
    d = report.summary_dict()
    assert d["elapsed_seconds"] == 4.0


def test_summary_dict_is_json_serialisable():
    report = _make_report(SyncStatus.CREATED)
    report.elapsed_seconds = 0.5
    dumped = json.dumps(report.summary_dict())
    loaded = json.loads(dumped)
    assert loaded["created"] == 1


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


def _make_engine_mock(report: SyncReport):
    """Return a SyncEngine mock whose .run() returns *report*."""
    engine = MagicMock()
    engine.run.return_value = report
    return engine


def _patched_runner(report: SyncReport):
    """Context manager that patches SyncEngine, GitHubClient, ConfluenceClient, load_config."""
    from unittest.mock import patch
    from docsync.config import DocSyncConfig
    cfg = MagicMock(spec=DocSyncConfig)
    cfg.confluence_base_url = "https://example.atlassian.net"
    cfg.confluence_user = "user@example.com"
    cfg.confluence_token = "token"
    cfg.batch_size = 5
    cfg.space_mappings = []
    cfg.dry_run = False
    cfg.resolve_active_spaces.return_value = ["DOCS"]
    cfg.model_copy.return_value = cfg

    patches = [
        patch("docsync.main.load_config", return_value=cfg),
        patch("docsync.main.GitHubClient"),
        patch("docsync.main.ConfluenceClient"),
        patch("docsync.main.SpaceRouter"),
        patch("docsync.main.SyncEngine", return_value=_make_engine_mock(report)),
    ]
    return patches


def _invoke_sync(report: SyncReport, extra_args: list[str] | None = None):
    from docsync.main import cli
    runner = CliRunner()
    args = [
        "sync",
        "--owner", "acme",
        "--repo", "docs",
        "--sha", "abc1234567890",
        "--config", "fake.yml",
    ]
    if extra_args:
        args.extend(extra_args)

    patches = _patched_runner(report)
    started = []
    for p in patches:
        started.append(p.start())
    # Disable log_jsonlines and write_github_step_summary to keep output clean
    report.log_jsonlines = MagicMock()
    report.write_github_step_summary = MagicMock()
    try:
        result = runner.invoke(cli, args)
    finally:
        for p in patches:
            p.stop()
    return result


def test_table_summary_contains_labels():
    report = _make_report(SyncStatus.CREATED, SyncStatus.UPDATED, SyncStatus.SKIPPED)
    result = _invoke_sync(report)
    assert "SUMMARY" in result.output
    assert "Created:" in result.output
    assert "Updated:" in result.output
    assert "Archived:" in result.output
    assert "Skipped:" in result.output
    assert "Errors:" in result.output
    assert "Elapsed:" in result.output


def test_table_summary_correct_counts():
    report = _make_report(SyncStatus.CREATED, SyncStatus.CREATED, SyncStatus.SKIPPED)
    result = _invoke_sync(report)
    assert "Created:  2" in result.output
    assert "Skipped:  1" in result.output
    assert "Errors:   0" in result.output


def test_dry_run_label_in_summary():
    report = _make_report(SyncStatus.SKIPPED)
    result = _invoke_sync(report, extra_args=["--dry-run"])
    assert "DRY RUN" in result.output


def test_json_output_format():
    report = _make_report(SyncStatus.CREATED, SyncStatus.UPDATED)
    report.elapsed_seconds = 1.0
    result = _invoke_sync(report, extra_args=["--output-format", "json"])
    # Find the JSON line in output
    json_line = None
    for line in result.output.splitlines():
        line = line.strip()
        if line.startswith("{") and "created" in line:
            json_line = line
            break
    assert json_line is not None, f"No JSON summary line found in:\n{result.output}"
    data = json.loads(json_line)
    assert data["created"] == 1
    assert data["updated"] == 1
    assert "elapsed_seconds" in data


def test_exit_code_zero_no_errors():
    report = _make_report(SyncStatus.CREATED)
    result = _invoke_sync(report)
    assert result.exit_code == 0


def test_exit_code_one_on_errors():
    report = _make_report(SyncStatus.FAILED, SyncStatus.CREATED)
    result = _invoke_sync(report)
    assert result.exit_code == 1
