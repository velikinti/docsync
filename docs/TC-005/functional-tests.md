# Functional Tests — TC-005: Archive Confluence Pages on Source File Deletion

## Overview
These tests validate TC-005's archive-on-delete feature against a live Confluence Cloud
instance — no mocks. Each test creates real pages using `ConfluenceClient.create_page()`,
exercises the `SyncEngine` archive path, and asserts against actual Confluence API responses.
All tests require Confluence credentials set as environment variables.

---

## Environment Setup

### Required env vars

| Variable | Purpose |
|---|---|
| `CONFLUENCE_API_TOKEN` | API token for Confluence Cloud |
| `CONFLUENCE_USER` | Confluence user email |
| `CONFLUENCE_BASE_URL` | e.g. `https://your-org.atlassian.net` |
| `CONFLUENCE_TEST_SPACE` | Space key for test pages (default: `MFS`) |
| `CONFLUENCE_ROOT_PAGE_ID` | Parent page ID under which test pages are created |

### Run

```powershell
# Full TC-005 functional suite
pytest tests/functional/test_tc_005_e2e.py -v --tb=short

# Single test
pytest tests/functional/test_tc_005_e2e.py::TestArchiveHappyPath::test_deleted_file_archived -v

# Skip functional tests (run unit tests only)
pytest tests/ -v --ignore=tests/functional
```

---

## Test Scenarios

| ID | FR(s) | Class | Method | Type | Title | Assert |
|----|-------|-------|--------|------|-------|--------|
| FT-01 | FR-01, FR-03, FR-04, FR-05 | `TestArchiveHappyPath` | `test_deleted_file_archived` | happy | DELETED file with existing Confluence page → ARCHIVED | `result.status == ARCHIVED`, page no longer in current-page search |
| FT-02 | FR-05, FR-11 | `TestArchiveHappyPath` | `test_archived_count_in_sync_report` | happy | SyncReport.archived_count and summary_dict() reflect archive | `report.archived_count == 1`, `summary_dict()["archived"] == 1` |
| FT-03 | NFR-04 | `TestArchiveHappyPath` | `test_archive_idempotent_second_call_is_no_op` | boundary | Second archive call on same page is a no-op (404 = success) | No exception raised on second `archive_page()` call |
| FT-04 | FR-06 | `TestArchiveGuards` | `test_no_confluence_page_skips_not_errors` | negative | DELETED file with no Confluence page → SKIPPED, not FAILED | `result.status == SKIPPED`, `result.error` contains "not found" |
| FT-05 | FR-07 | `TestArchiveGuards` | `test_archive_on_delete_false_skips_and_leaves_page` | negative | `archive_on_delete=False` guard → SKIPPED, page stays current | `result.status == SKIPPED`, page still findable in Confluence |
| FT-06 | FR-09 | `TestArchiveGuards` | `test_dry_run_skips_delete_page_survives` | negative | `dry_run=True` → SKIPPED with `error="dry-run"`, zero Confluence writes | `result.error == "dry-run"`, page still findable |
| FT-07 | FR-02 | `TestGlobFilter` | `test_excluded_path_not_archived` | negative | Path matching `exclude_globs` does not pass glob filter | `_matches_globs()` returns False; page remains current in Confluence |
| FT-08 | FR-08, DD-TC005-03 | `TestRenamedFile` | `test_renamed_archives_old_path_and_creates_new_page` | happy | RENAMED event archives previous_path and creates new path | Old path → `find_page_by_property` returns None; new path returns new `page_id` |
| FT-09 | FR-08, DD-TC005-03 | `TestRenamedFile` | `test_renamed_with_missing_old_page_still_creates_new` | negative | RENAMED with no existing old page → upsert still succeeds | `result.status in (CREATED, UPDATED)` despite archive SKIPPED for ghost path |

---

## Traceability Matrix

| FR | Requirement (truncated) | Scenario(s) | Test Method |
|----|------------------------|-------------|-------------|
| FR-01 | The system SHALL detect file deletions by reading `ChangeType.DELETED` entries | FT-01 | `TestArchiveHappyPath::test_deleted_file_archived` |
| FR-02 | The system SHALL apply glob filters to deleted file paths | FT-07 | `TestGlobFilter::test_excluded_path_not_archived` |
| FR-03 | The system SHALL locate the page via `docsync:source_path` property | FT-01 | `TestArchiveHappyPath::test_deleted_file_archived` |
| FR-04 | The system SHALL archive via `archive_page()` (Confluence trash) | FT-01 | `TestArchiveHappyPath::test_deleted_file_archived` |
| FR-05 | The system SHALL record `SyncStatus.ARCHIVED` in `SyncReport` | FT-01, FT-02 | `test_deleted_file_archived`, `test_archived_count_in_sync_report` |
| FR-06 | The system SHALL emit warning and `SKIPPED` when no page found | FT-04 | `TestArchiveGuards::test_no_confluence_page_skips_not_errors` |
| FR-07 | The system SHALL support `archive_on_delete=false` guard | FT-05 | `TestArchiveGuards::test_archive_on_delete_false_skips_and_leaves_page` |
| FR-08 | RENAMED: archive previous_path + upsert new path | FT-08, FT-09 | `TestRenamedFile::test_renamed_*` |
| FR-09 | `dry_run=True` → SKIPPED, no Confluence calls | FT-06 | `TestArchiveGuards::test_dry_run_skips_delete_page_survives` |
| FR-10 | Directory-type pages → `HierarchyManager.archive_directory()` | — | Deferred: requires HierarchyManager setup (out of scope for initial functional suite) |
| FR-11 | `SyncReport.archived_count` surfaced in `summary_dict()` | FT-02 | `TestArchiveHappyPath::test_archived_count_in_sync_report` |
| NFR-04 | Archive is idempotent; 404 = success | FT-03 | `TestArchiveHappyPath::test_archive_idempotent_second_call_is_no_op` |

---

## Test Files

| File | Purpose |
|------|---------|
| `tests/functional/conftest.py` | Session/function fixtures: `real_confluence`, `base_cfg`, `cleanup_pages`, credential guard |
| `tests/functional/test_tc_005_e2e.py` | 9 functional test methods across 4 test classes |

---

## Limitations

- Tests create and archive real Confluence pages — run only against a dedicated test space (`CONFLUENCE_TEST_SPACE`), never production
- All tests require valid API credentials via environment variables; they skip automatically if credentials are absent
- Confluence Cloud rate-limits at ~300 req/min; run tests serially (default pytest), not in parallel
- FR-10 (directory-type archive) is not covered — requires `HierarchyManager.prefetch_page_cache()` setup and a parent/child page hierarchy in the test space
- The glob filter test (FT-07) validates `_matches_globs` directly since the glob check lives in `_run_async` (full sync loop), not in `_handle_delete`
