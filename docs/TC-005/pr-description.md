# PR: Archive Confluence Pages on Source File Deletion (TC-005)

## Summary

This PR implements automatic archiving of Confluence pages when their source Markdown files are deleted from (or renamed within) the GitHub repository. When a developer deletes a `.md` file and pushes to `main`, DocSync now calls `ConfluenceClient.archive_page()` to move the corresponding Confluence page to trash — keeping the Confluence space in sync with the repo and preventing stale pages from accumulating. The feature is controlled by a new `archive_on_delete` boolean config field (default: `true`), preserving backward compatibility for all existing `.docsync.yml` files. This implementation was driven end-to-end by an 8-phase Agentic SDLC pipeline using Claude Code.

---

## Changes Made

### SDLC Artifacts

| File | Phase | Description |
|------|-------|-------------|
| `docs/TC-005/requirements.md` | 1 — Requirements | 11 FR + 5 NFR; agent Q&A covering detection mechanism, glob filtering, page-not-found, recoverable vs. hard delete, `archive_on_delete` opt-out, and RENAMED handling |
| `docs/TC-005/architecture.md` | 2 — Architecture | Component design for archive flow; data flow, traceability matrix, error handling strategy; updated in Phase 3 for DD-TC005-03 |
| `docs/TC-005/design-review.md` | 3 — Design Review | 5 risks (RISK-01..05), 3 gaps (GAP-01..03), 5 design decisions (DD-TC005-01..05); architecture sections 3.2, 3.5, 7, 8 updated |
| `docs/TC-005/impl-plan.md` | 4 — Impl Planning | 6 tasks (T-01..T-06); dependency graph; critical path 150 min |
| `docs/TC-005/code-review.md` | 6 — Code Review | 4 findings (CR-01 MEDIUM, CR-02 MEDIUM, CR-03 LOW, CR-04 LOW); verdict PASS WITH MINOR ISSUES |
| `docs/TC-005/verification.md` | 7 — Verification | 129 passed, 79% coverage, security scan CLEAN; verdict PASS WITH CONDITIONS |

### Source Code

| File | Change | FR(s) / Design Decision |
|------|--------|------------------------|
| `src/docsync/config.py` | Added `archive_on_delete: bool = Field(default=True, ...)` at line 25 | FR-07, DD-TC005-01 — pydantic default preserves backward compat |
| `src/docsync/sync.py` | `_handle_delete` (lines 445-463): early-return guard when `archive_on_delete=False` + replaced silent skip with `log.warning("page_not_found_for_delete")` | FR-07, FR-06 |
| `src/docsync/sync.py` | `_process_file` (lines 338-346): RENAMED branch that calls `_handle_delete(previous_path)` in an isolated `try/except`, then falls through unconditionally to `_handle_upsert` | FR-08, DD-TC005-03 |

### Infrastructure

No infrastructure changes. No new dependencies, no new CLI flags, no workflow modifications. All changes are confined to `src/docsync/` and `tests/`.

### Tests

| File | Change | What It Covers |
|------|--------|----------------|
| `tests/test_config.py` | Added `TestArchiveOnDeleteConfig` (4 tests) | `archive_on_delete` field: default `True`, explicit `False`, explicit `True`, base_config fixture regression |
| `tests/test_sync_delete.py` | New file — `TestArchiveOnDelete` (3 tests) + `TestRenamedFileHandling` (5 tests) | FR-06 (page-not-found warning), FR-07 (flag skip + debug log), FR-08 (archive previous + upsert new, archive failure isolation, dry-run, no-previous-path guard), FR-09 (dry-run skip) |

---

## Test Evidence

*(Verbatim from `docs/TC-005/verification.md`)*

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.0.2, pluggy-1.6.0 -- python.exe
rootdir: C:\Projects\Capstone_Project\Claude-Capstone-Project
asyncio: mode=Mode.STRICT

tests/test_config.py::TestLegacyBackwardCompat::test_space_key_promoted_to_space_keys PASSED
tests/test_config.py::TestLegacyBackwardCompat::test_space_key_preserved_alongside_space_keys PASSED
tests/test_config.py::TestLegacyBackwardCompat::test_existing_base_config_valid PASSED
tests/test_config.py::TestLegacyBackwardCompat::test_strip_trailing_slash_on_url PASSED
tests/test_config.py::TestMultiSpaceFields::test_space_keys_list_accepted PASSED
tests/test_config.py::TestMultiSpaceFields::test_space_mappings_accepted PASSED
tests/test_config.py::TestMultiSpaceFields::test_space_keys_not_promoted_when_already_set PASSED
tests/test_config.py::TestMultiSpaceFields::test_missing_all_space_fields_raises PASSED
tests/test_config.py::TestMultiSpaceFields::test_space_mappings_alone_is_sufficient PASSED
tests/test_config.py::TestResolveActiveSpaces::test_cli_override_takes_precedence PASSED
tests/test_config.py::TestResolveActiveSpaces::test_space_keys_returned_when_no_override PASSED
tests/test_config.py::TestResolveActiveSpaces::test_legacy_space_key_returned_when_no_space_keys PASSED
tests/test_config.py::TestResolveActiveSpaces::test_mappings_values_returned_as_fallback PASSED
tests/test_config.py::TestResolveActiveSpaces::test_cli_override_as_empty_list_returns_empty PASSED
tests/test_config.py::TestResolveActiveSpaces::test_cli_override_multi_space PASSED
tests/test_config.py::TestArchiveOnDeleteConfig::test_archive_on_delete_defaults_to_true PASSED
tests/test_config.py::TestArchiveOnDeleteConfig::test_archive_on_delete_false_accepted PASSED
tests/test_config.py::TestArchiveOnDeleteConfig::test_archive_on_delete_true_explicit PASSED
tests/test_config.py::TestArchiveOnDeleteConfig::test_base_config_fixture_has_archive_on_delete_true PASSED
tests/test_confluence_client.py::TestFindPage::test_finds_page_by_source_path PASSED
tests/test_confluence_client.py::TestFindPage::test_returns_none_when_not_found PASSED
tests/test_confluence_client.py::TestFindPage::test_raises_on_api_error PASSED
tests/test_confluence_client.py::TestCreatePage::test_creates_page_successfully PASSED
tests/test_confluence_client.py::TestUpdatePage::test_updates_page_successfully PASSED
tests/test_confluence_client.py::TestArchivePage::test_archives_page PASSED
tests/test_confluence_client.py::TestArchivePage::test_archive_idempotent_on_404 PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessFound::test_space_found_and_writable PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessFound::test_space_found_but_read_only PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessFound::test_space_found_but_no_permissions_entries PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessNotFound::test_space_not_found_empty_results PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessNotFound::test_spaces_endpoint_returns_403 PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessNotFound::test_spaces_endpoint_returns_404 PASSED
tests/test_confluence_spaces.py::TestCheckSpaceAccessPermissionsError::test_permissions_endpoint_returns_403 PASSED
tests/test_converter.py::TestConvert::test_basic_markdown_converts PASSED
tests/test_converter.py::TestConvert::test_code_fence_becomes_confluence_macro PASSED
tests/test_converter.py::TestConvert::test_table_converts PASSED
tests/test_converter.py::TestConvert::test_relative_image_extracted PASSED
tests/test_converter.py::TestConvert::test_absolute_image_not_extracted PASSED
tests/test_converter.py::TestConvert::test_invalid_xhtml_triggers_fallback PASSED
tests/test_converter.py::TestConvert::test_empty_markdown PASSED
tests/test_converter.py::TestConvert::test_bold_italic PASSED
tests/test_converter.py::TestApplyAttachmentUrls::test_rewrites_src_after_upload PASSED
tests/test_converter.py::TestApplyAttachmentUrls::test_no_images_returns_unchanged_body PASSED
tests/test_github_client.py::TestListChangedFiles::test_lists_added_and_modified_files PASSED
tests/test_github_client.py::TestListChangedFiles::test_raises_on_api_error PASSED
tests/test_github_client.py::TestGetFileContent::test_decodes_base64_content PASSED
tests/test_github_client.py::TestGetFileContent::test_raises_file_not_found PASSED
tests/test_github_client.py::TestFetchFilesBatch::test_fetches_multiple_files PASSED
tests/test_github_client.py::TestFetchFilesBatch::test_skips_missing_files PASSED
tests/test_hierarchy.py::TestPrefetchPageCache::test_populates_cache_from_confluence PASSED
tests/test_hierarchy.py::TestPrefetchPageCache::test_empty_space_sets_empty_cache PASSED
tests/test_hierarchy.py::TestResolveParentIdSingleLevel::test_top_level_file_returns_root PASSED
tests/test_hierarchy.py::TestResolveParentIdSingleLevel::test_one_level_deep_creates_parent PASSED
tests/test_hierarchy.py::TestResolveParentIdSingleLevel::test_existing_parent_not_recreated PASSED
tests/test_hierarchy.py::TestResolveParentIdMultiLevel::test_three_level_chain_creates_intermediate_pages PASSED
tests/test_hierarchy.py::TestResolveParentIdMultiLevel::test_second_call_uses_cache PASSED
tests/test_hierarchy.py::TestConcurrentDirectoryCreation::test_lock_prevents_duplicate_page_creation PASSED
tests/test_hierarchy.py::TestDryRun::test_dry_run_returns_synthetic_id PASSED
tests/test_hierarchy.py::TestDryRun::test_dry_run_deterministic_for_same_path PASSED
tests/test_hierarchy.py::TestDryRun::test_dry_run_does_not_call_confluence_write PASSED
tests/test_hierarchy.py::TestArchiveDirectory::test_archives_root_and_descendants PASSED
tests/test_hierarchy.py::TestArchiveDirectory::test_no_page_found_returns_empty PASSED
tests/test_hierarchy.py::TestArchiveDirectory::test_dry_run_does_not_call_archive PASSED
tests/test_hierarchy.py::TestMaxArchiveDepth::test_depth_limit_stops_recursion PASSED
tests/test_space_router.py::TestEmptyRouter::test_is_empty_true PASSED
tests/test_space_router.py::TestEmptyRouter::test_resolve_returns_none PASSED
tests/test_space_router.py::TestEmptyRouter::test_all_spaces_empty PASSED
tests/test_space_router.py::TestBasicRouting::test_resolve_exact_prefix PASSED
tests/test_space_router.py::TestBasicRouting::test_resolve_nested_path PASSED
tests/test_space_router.py::TestBasicRouting::test_resolve_no_match_returns_none PASSED
tests/test_space_router.py::TestBasicRouting::test_all_spaces_unique_ordered PASSED
tests/test_space_router.py::TestKeyNormalisation::test_key_without_trailing_slash_normalised PASSED
tests/test_space_router.py::TestKeyNormalisation::test_key_with_trailing_slash_unchanged PASSED
tests/test_space_router.py::TestKeyNormalisation::test_both_forms_equivalent PASSED
tests/test_space_router.py::TestLongestPrefixMatching::test_longer_prefix_wins PASSED
tests/test_space_router.py::TestLongestPrefixMatching::test_shorter_prefix_matches_non_api_path PASSED
tests/test_space_router.py::TestLongestPrefixMatching::test_three_levels_longest_wins PASSED
tests/test_space_router.py::TestLongestPrefixMatching::test_identical_length_prefixes_different_spaces PASSED
tests/test_space_router.py::TestEdgeCases::test_path_with_no_slash_does_not_match_prefix PASSED
tests/test_space_router.py::TestEdgeCases::test_is_empty_false_when_has_mappings PASSED
tests/test_space_router.py::TestEdgeCases::test_multiple_spaces_all_spaces_deduped PASSED
tests/test_sync.py::TestSyncEngineHappyPath::test_creates_new_page_for_added_file PASSED
tests/test_sync.py::TestSyncEngineHappyPath::test_updates_existing_page PASSED
tests/test_sync.py::TestSyncEngineHappyPath::test_archives_deleted_file PASSED
tests/test_sync.py::TestSyncEngineHappyPath::test_skips_deleted_file_not_in_confluence PASSED
tests/test_sync.py::TestDryRun::test_dry_run_skips_all_writes PASSED
tests/test_sync.py::TestGlobFiltering::test_excluded_files_are_skipped PASSED
tests/test_sync.py::TestPartialFailure::test_failure_on_one_file_does_not_stop_others PASSED
tests/test_sync.py::TestSyncReport::test_counts_are_correct PASSED
tests/test_sync_delete.py::TestArchiveOnDelete::test_archive_on_delete_false_skips PASSED
tests/test_sync_delete.py::TestArchiveOnDelete::test_archive_on_delete_false_logs_debug PASSED
tests/test_sync_delete.py::TestArchiveOnDelete::test_page_not_found_logs_warning PASSED
tests/test_sync_delete.py::TestRenamedFileHandling::test_renamed_archives_previous_path PASSED
tests/test_sync_delete.py::TestRenamedFileHandling::test_renamed_upserts_new_path PASSED
tests/test_sync_delete.py::TestRenamedFileHandling::test_renamed_archive_failure_does_not_block_upsert PASSED
tests/test_sync_delete.py::TestRenamedFileHandling::test_renamed_dry_run_skips_archive_and_upsert PASSED
tests/test_sync_delete.py::TestRenamedFileHandling::test_renamed_no_previous_path_skips_archive PASSED
tests/test_sync_spaces.py::TestPreflightAbort::test_raises_when_space_not_found PASSED
tests/test_sync_spaces.py::TestPreflightAbort::test_no_files_processed_on_preflight_failure PASSED
tests/test_sync_spaces.py::TestPreflightContinueOnError::test_failing_space_dropped_others_continue PASSED
tests/test_sync_spaces.py::TestPreflightContinueOnError::test_all_spaces_fail_returns_empty_report PASSED
tests/test_sync_spaces.py::TestFileRouting::test_file_mapped_to_active_space_is_synced PASSED
tests/test_sync_spaces.py::TestFileRouting::test_file_mapped_to_inactive_space_is_skipped PASSED
tests/test_sync_spaces.py::TestFileRouting::test_unmapped_file_is_skipped_with_warning PASSED
tests/test_sync_spaces.py::TestFileRouting::test_mixed_files_routed_correctly PASSED
tests/test_sync_spaces.py::TestLegacySingleSpaceMode::test_legacy_engine_works_without_router PASSED
tests/test_sync_spaces.py::TestLegacySingleSpaceMode::test_legacy_find_page_uses_space_key PASSED
tests/test_sync_spaces.py::TestSyncReportBySpace::test_by_space_groups_correctly PASSED
tests/test_sync_spaces.py::TestSyncReportBySpace::test_by_space_empty_report PASSED
tests/test_sync_spaces.py::TestSyncReportBySpace::test_by_space_all_same_space PASSED
tests/test_sync_summary.py::test_created_count PASSED
tests/test_sync_summary.py::test_updated_count PASSED
tests/test_sync_summary.py::test_archived_count PASSED
tests/test_sync_summary.py::test_skipped_count PASSED
tests/test_sync_summary.py::test_error_count PASSED
tests/test_sync_summary.py::test_all_zeros PASSED
tests/test_sync_summary.py::test_backward_compat_skip_count PASSED
tests/test_sync_summary.py::test_backward_compat_failure_count PASSED
tests/test_sync_summary.py::test_success_count_includes_created_updated_archived PASSED
tests/test_sync_summary.py::test_summary_dict_keys PASSED
tests/test_sync_summary.py::test_summary_dict_values PASSED
tests/test_sync_summary.py::test_summary_dict_elapsed_rounded_two_dp PASSED
tests/test_sync_summary.py::test_summary_dict_is_json_serialisable PASSED
tests/test_sync_summary.py::test_table_summary_contains_labels PASSED
tests/test_sync_summary.py::test_table_summary_correct_counts PASSED
tests/test_sync_summary.py::test_dry_run_label_in_summary PASSED
tests/test_sync_summary.py::test_json_output_format PASSED
tests/test_sync_summary.py::test_exit_code_zero_no_errors PASSED
tests/test_sync_summary.py::test_exit_code_one_on_errors PASSED

============================ 129 passed in 11.37s =============================
```

**Coverage:**

```
Name                               Stmts   Miss  Cover   Missing
----------------------------------------------------------------
src\docsync\__init__.py                8      0   100%
src\docsync\config.py                 64     10    84%   47, 54, 58, 67, 81-86
src\docsync\confluence_client.py     208     91    56%   127-128, 157-158, 179, 238-253, 265-306,
                                                         316-341, 346-355, 360-378
src\docsync\converter.py              75      3    96%   125-127
src\docsync\github_client.py          73      6    92%   44-47, 91, 98
src\docsync\hierarchy.py              76      0   100%
src\docsync\main.py                   83     13    84%   82-85, 89-91, 114, 124-126, 162, 166
src\docsync\space_router.py           17      0   100%
src\docsync\sync.py                  253     59    77%   105-106, 119-155, 160, 178-186, 252, 350,
                                                         385, 389-397, 400, 469-477, 491-498
----------------------------------------------------------------
TOTAL                                857    182    79%
============================ 129 passed in 9.36s =============================
```

---

## Known Limitations

### From Code Review (Phase 6)

**CR-01 (MEDIUM) — Missing success log for RENAMED archive.**
`sync.py` lines 338–346: when a RENAMED event successfully archives the `previous_path`, the event is completely silent — no log entry, no SyncReport entry. Only the failure case (`log.warning("rename_archive_failed", ...)`) is logged. The design-review RISK-03 mitigation explicitly required `log.info("rename_archived_previous", previous_path=..., page_id=...)` on success; this was not implemented.
*Why deferred:* Discovered in Phase 6 review; Phase 7 verified no data loss — the archive does execute correctly. Fix is recommended before merge.

**CR-02 (MEDIUM) — FR-10 directory archive path has no sync-level test.**
`sync.py` lines 469–477 (`if path_type == "directory" and hierarchy is not None`) has 0% test coverage in TC-005's test suite. `conftest.py` hard-codes `get_page_property.return_value = "file"`, bypassing the directory branch in all current tests.
*Why deferred:* The code path is pre-existing (from TC-004's `DD-TC004-02`). `HierarchyManager.archive_directory()` is independently tested at 100% in `test_hierarchy.py`. A sync-level test requires injecting a `HierarchyManager` mock into `SyncEngine`, which is a larger test-fixture change; tracked as a follow-on.

### From Design Review (Phase 3)

**RISK-02 / GAP-03 — `_handle_delete` bypasses `HierarchyManager` prefetch cache.**
`sync.py:453-455` calls `self._cf.find_page_by_property()` directly for each deleted file, executing a full paginated scan rather than checking the startup prefetch cache. For a space with thousands of pages and a commit deleting many files, this adds unnecessary API load.
*Why deferred:* Pre-existing behavior shared by all delete operations. Fixing it requires adding a `HierarchyManager.lookup_page_id(source_path)` public method — a clean but broader change outside TC-005's scope.

**RISK-04 — Bulk deletion commits may be slow under Confluence rate limits.**
50 deletions × 3 API calls each = 150 calls; Confluence Cloud rate-limits at ~300 req/min. Large restructuring commits will be noticeably slow.
*Why accepted:* Consistent with NFR-05. The `asyncio.Semaphore(batch_size)` pattern could be extended to Confluence operations in a future performance pass.

**RISK-05 — RENAMED where new path falls outside `include_globs` may leave stale pages.**
If `docs/old.md` matches `include_globs` but `docs/new.md` does not, the rename event is filtered out entirely and the old Confluence page is never archived.
*Why deferred:* FR-02 only specifies applying glob filters to deleted file paths. The cross-glob rename edge case is best handled alongside broader glob-filter refinements in a future PR.

---

## Reviewer Checklist

**Functional Requirements:**

- [ ] **FR-01** — `sync.py:335`: `if changed.change_type == ChangeType.DELETED` dispatches to `_handle_delete`
- [ ] **FR-02** — `sync.py:273-276`: `_matches_globs()` called on all change types before dispatch (pre-existing, unchanged)
- [ ] **FR-03** — `sync.py:453-455`: page lookup uses `find_page_by_property(space_key, "docsync:source_path", path)` — NOT title (DD-01 enforced)
- [ ] **FR-04** — `sync.py:485`: `self._cf.archive_page(existing_id)` called for file-type deletions (Confluence trash, recoverable)
- [ ] **FR-05** — `sync.py:486-488`: returns `SyncResult(status=SyncStatus.ARCHIVED, page_id=existing_id)`
- [ ] **FR-06** — `sync.py:456-463`: when `find_page_by_property` returns `None`, emits `log.warning("page_not_found_for_delete", path=..., space_key=...)` and returns `SyncStatus.SKIPPED`
- [ ] **FR-07** — `config.py:25`: `archive_on_delete: bool = Field(default=True, ...)` present; `sync.py:445-450`: guard returns `SKIPPED` + `log.debug("archive_on_delete_disabled")` when `False`
- [ ] **FR-08** — `sync.py:338-346`: RENAMED branch calls `_handle_delete(previous_path)` in isolated `try/except`; then falls through unconditionally to `_handle_upsert` for new path
- [ ] **FR-09** — `sync.py:440-443`: dry_run guard in `_handle_delete` returns `SKIPPED` before any API call
- [ ] **FR-10** — `sync.py:468-482`: `path_type == "directory"` delegates to `hierarchy.archive_directory(path)` (pre-existing DD-TC004-02)
- [ ] **FR-11** — `SyncReport.archived_count` pre-existing; verify `test_sync_summary.py::test_archived_count` and `test_summary_dict_values` pass

**Non-Functional Requirements:**

- [ ] **NFR-01 (Retry)** — `confluence_client.py:168`: `@_RETRY` decorator on `archive_page` (3 attempts, exponential 2–30 s back-off, on `RuntimeError`)
- [ ] **NFR-03 (No secrets in logs)** — `sync.py:342-346`: `error=str(exc)` sourced from `RuntimeError` already sanitised by `_sanitised_error()`; run: `grep -rn "token\s*=" src/ | grep -v "os\.environ\|sanitise\|def __init__"` — should be empty
- [ ] **NFR-04 (Idempotency)** — `confluence_client.py:177-178`: 404 on DELETE returns silently (page already gone — no retry, no error)

**Design Decisions:**

- [ ] **DD-TC005-01** — `config.py:25`: `archive_on_delete` defaults to `True`; existing `.docsync.yml` files need no changes — verify by omitting the field and confirming `DocSyncConfig` builds without error
- [ ] **DD-TC005-02** — `sync.py:338-357`: RENAMED returns a single `SyncResult` for the upsert of the new path; archive of `previous_path` is fire-and-forget (logged only, not in SyncReport)
- [ ] **DD-TC005-03** — `sync.py:338-346`: isolated `try/except` around RENAMED archive prevents archive failure from blocking upsert and prevents error misattribution
- [ ] **DD-TC005-04** — `sync.py:453-455`: `find_page_by_property` called directly (live API); HierarchyManager cache not consulted — pre-existing gap, not worsened
- [ ] **DD-TC005-05** — glob filter applied to `changed.path` (new path); `changed.previous_path` is not filtered separately

**Test and Quality Gates:**

- [ ] Run `pytest tests/ -v --tb=short` — must show **129 passed, 0 failed**
- [ ] Run `pytest tests/ --cov=src/docsync --cov-report=term-missing` — must show total ≥ 70%
- [ ] Verify `tests/test_sync_delete.py` contains `TestArchiveOnDelete` (3 tests) and `TestRenamedFileHandling` (5 tests)
- [ ] Run dry-run: `docsync sync --dry-run --config .docsync.yml` — should print `DRY RUN — no writes to Confluence` (exit code may be 1 if Confluence space is absent in the test environment — this is expected pre-flight behavior, not a code defect)

**Backward Compatibility:**

- [ ] Omit `archive_on_delete` from `.docsync.yml` — existing config files load without error; behavior is `True` (archive enabled)
- [ ] Run `tests/test_config.py::TestArchiveOnDeleteConfig::test_archive_on_delete_defaults_to_true` — must PASS
- [ ] Verify no pre-existing tests regressed: `tests/test_sync.py`, `tests/test_confluence_client.py`, `tests/test_hierarchy.py` all pass unchanged
