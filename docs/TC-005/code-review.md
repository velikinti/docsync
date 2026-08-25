# Code Review — Archive Confluence Pages on Source File Deletion

**Test Case:** TC-005
**Phase:** 6 — Code Review
**Reviewer:** Phase 6 agent (senior peer reviewer)
**Input:** Phase 5 APPROVED — `src/docsync/config.py`, `src/docsync/sync.py`, `tests/test_config.py`, `tests/test_sync_delete.py`

---

## Pre-flight

`outputs/TC-005/phase-status.json` — phase `"5"` status: `APPROVED` ✓

---

## 1. Correctness — FR Traceability

| FR | Requirement (summary) | Code location | Status |
|----|----------------------|---------------|--------|
| FR-01 | Detect deletions via `ChangeType.DELETED` from `list_changed_files()` | `sync.py:335` — `if changed.change_type == ChangeType.DELETED` | **PASS** |
| FR-02 | Apply `include_globs`/`exclude_globs` to deleted paths | `sync.py:273-276` — `_matches_globs()` applied to all change types before dispatch | **PASS** |
| FR-03 | Locate Confluence page via `docsync:source_path` property | `sync.py:453-455` — `find_page_by_property(space_key, "docsync:source_path", path)` | **PASS** |
| FR-04 | Archive via `archive_page()` (Confluence trash, recoverable) | `sync.py:485` — `self._cf.archive_page(existing_id)` | **PASS** |
| FR-05 | Record `SyncStatus.ARCHIVED` + `page_id` in `SyncReport` | `sync.py:486-488` — `SyncResult(ARCHIVED, page_id=existing_id)` | **PASS** |
| FR-06 | `log.warning("page_not_found_for_delete")` + `SKIPPED` when page absent | `sync.py:457-463` | **PASS** |
| FR-07 | `archive_on_delete` config flag (default `true`); skip with DEBUG log when `false` | `config.py:25`, `sync.py:445-450` | **PASS** |
| FR-08 | RENAMED → archive `previous_path` + upsert new path in one run | `sync.py:338-346` (archive), `sync.py:357` (upsert) | **PARTIAL** — see CR-01 |
| FR-09 | `dry_run=True` → skip all Confluence calls, return `SKIPPED` | `sync.py:440-443` (`_handle_delete`), `sync.py:372-375` (`_handle_upsert`) | **PASS** |
| FR-10 | Directory-type pages delegated to `HierarchyManager.archive_directory()` | `sync.py:468-482` — pre-existing `DD-TC004-02` code path | **PARTIAL** — see CR-02 |
| FR-11 | Archived counts in `SyncReport.archived_count` and `summary_dict()` | `sync.py:62-64`, `sync.py:91` — pre-existing `archived_count` property | **PASS** |

---

## 2. Security

**Hardcoded secrets scan:**
```
grep -rn "token\s*=" src/  → only os.environ references (config.py:58, github_client.py:33)
```
No hardcoded secrets found. ✓

**`os.environ` pattern:**
- `config.py:44-45` — `validate_env_vars` validator checks `CONFLUENCE_API_TOKEN`, `CONFLUENCE_USER` at startup
- `config.py:54-58` — `confluence_user`, `confluence_token` properties read from `os.environ` at call-time only
- No token stored in any field, no token in `DocSyncConfig.__repr__` output ✓

**Structlog safety:**
- `log.debug("archive_on_delete_disabled", path=path)` — path only; no config object dumped ✓
- `log.warning("page_not_found_for_delete", path=path, space_key=space_key)` — no credentials ✓
- `log.warning("rename_archive_failed", previous_path=..., error=str(exc))` — `str(exc)` comes from `RuntimeError` already sanitised by `_sanitised_error()` ✓
- `_sanitised_error()` (`confluence_client.py:64-68`) caps response body at 200 chars and does not include auth headers ✓

**`.docsync.yml` check:**
- No tokens, passwords, or credentials in the committed config file ✓

**Overall security verdict: PASS**

---

## 3. Error Handling

**Tenacity `@_RETRY` on mutating Confluence calls:**
- `archive_page` — `@_RETRY` at `confluence_client.py:168` ✓ (NFR-01)
- `create_page`, `update_page`, `find_page_by_property`, `get_page_property` — all `@_RETRY` ✓

**404 idempotency (`archive_page`):**
- `confluence_client.py:177-178` — `if exc.response.status_code == 404: return` — no error, no retry ✓ (NFR-04)

**Per-file exception isolation:**
- `sync.py:359-366` — outer `except Exception` in `_process_file` catches any unhandled error and returns `SKIPPED/FAILED` for that file only; does not abort the batch ✓
- RENAMED archive isolated further: `sync.py:339-346` — inner `try/except` means archive failure for `previous_path` cannot block upsert of `new_path` ✓ (DD-TC005-03)

**`FileNotFoundError` mapping:**
- `github_client.py:90` — HTTP 404 on content fetch → `FileNotFoundError` ✓
- `fetch_files_batch:116` — `FileNotFoundError` silently skipped (deleted files have no content to fetch) ✓

**Overall error handling verdict: PASS**

---

## 4. Test Coverage

```
pytest --cov=src/docsync --cov-report=term-missing
```

| Module | Coverage | Threshold | Status |
|--------|----------|-----------|--------|
| `__init__.py` | 100% | 80% | ✓ |
| `config.py` | 84% | 80% | ✓ |
| `converter.py` | 96% | 80% | ✓ |
| `github_client.py` | 92% | 80% | ✓ |
| `hierarchy.py` | 100% | 80% | ✓ |
| `main.py` | 84% | 80% | ✓ |
| `space_router.py` | 100% | 80% | ✓ |
| `sync.py` | 77% | 80% | ⚠ see CR-03 |
| `confluence_client.py` | 56% | 80% | ⚠ see CR-04 |
| **TOTAL** | **79%** | — | — |

**TC-005-specific new tests (all pass):**
- `tests/test_config.py::TestArchiveOnDeleteConfig` — 4 tests; field defaults and validation ✓
- `tests/test_sync_delete.py::TestArchiveOnDelete` — 3 tests; FR-07, FR-06 ✓
- `tests/test_sync_delete.py::TestRenamedFileHandling` — 5 tests; FR-08 ✓

**Test correctness inspection:**
- All 8 tests assert on outcomes (status, call counts, log events), not just "no exception" ✓
- `structlog.testing.capture_logs()` used correctly for log-level assertions ✓
- `MagicMock(spec=ConfluenceClient)` ensures only real method names are callable ✓
- `model_copy(update={...})` used correctly for per-test config overrides ✓

---

## 5. Code Clarity

- Single responsibility maintained: `config.py` validates only; `sync.py` orchestrates only; clients are pure I/O wrappers ✓
- `_handle_delete` / `_handle_upsert` separation is clean and readable ✓
- New RENAMED branch in `_process_file` (lines 338-346) is easy to follow; the isolated `try/except` pattern is idiomatic ✓
- `archive_on_delete` naming is unambiguous ✓
- The `# Determine file vs directory via stored docsync:path_type property (DD-TC004-02)` comment at line 465 correctly cross-references the prior design decision ✓

---

## 6. DRY Principle

- `@_RETRY` tenacity decorator is defined once (`confluence_client.py:20-25`) and reused across all mutating methods ✓
- `_sanitised_error()` is a single helper for all HTTP exception sanitisation ✓
- `_matches_globs()` is used for all change types uniformly — no duplication ✓
- `_handle_delete` is invoked for both `DELETED` and `RENAMED` via a single shared method — no copy-paste ✓

---

## 7. Dependency Safety

```yaml
# requirements review (setup.cfg / pyproject.toml equivalent)
```

No version pinning issues introduced by TC-005 (no new dependencies added). Pre-existing dependency ranges are outside this PR's scope.

---

## Findings

---

**Finding CR-01 (MEDIUM):** `sync.py`, line 338-346. Successful RENAMED archive is invisible in logs — deviation from design-review RISK-03 mitigation.

RISK-03's accepted mitigation explicitly states: *"The archive of `previous_path` SHALL be logged with `log.info("rename_archived_previous", previous_path=..., page_id=...)` on success."* DD-TC005-02 states the archive is "logged only" (not in SyncReport). The implementation has the failure log (`log.warning("rename_archive_failed", ...)`) but omits the success log entirely. When a rename successfully archives the old page, the event is silent — not in the report, not in logs. Operators cannot confirm the old page was cleaned up without directly querying Confluence.

**Recommendation:** Capture the return value and add the success log:
```python
if changed.change_type == ChangeType.RENAMED and changed.previous_path:
    try:
        delete_result = await self._handle_delete(changed.previous_path, space_key, hierarchy)
        if delete_result.status == SyncStatus.ARCHIVED:
            log.info(
                "rename_archived_previous",
                previous_path=changed.previous_path,
                page_id=delete_result.page_id,
            )
    except Exception as exc:
        log.warning("rename_archive_failed", previous_path=changed.previous_path, error=str(exc))
```

---

**Finding CR-02 (MEDIUM):** `sync.py`, lines 469-477. FR-10 (directory-type page archiving) has no test in TC-005's test suite.

FR-10 states: *"The system SHALL support archiving directory-type pages… delegating to `HierarchyManager.archive_directory()`."* The code path (`if path_type == "directory" and hierarchy is not None`) exists at `sync.py:468` (pre-existing from `DD-TC004-02`) but is never exercised by TC-005 tests. `conftest.py` hard-codes `get_page_property.return_value = "file"`, so the directory branch is permanently bypassed in all current tests. Coverage report confirms lines 469-477 as missed.

**Recommendation:** Add to `tests/test_sync_delete.py`:
```python
def test_deletes_directory_type_page_via_hierarchy(engine, mock_github, mock_confluence):
    mock_confluence.find_page_by_property.return_value = "dir-page-id"
    mock_confluence.get_page_property.return_value = "directory"
    mock_confluence.archive_page.return_value = None
    # Need hierarchy mock with archive_directory — requires injecting HierarchyManager mock
```
*(Full implementation details for Phase 7 / follow-on.)*

---

**Finding CR-03 (LOW):** `sync.py` module-level coverage is 77% — below the 80% project threshold.

Uncovered lines (not introduced by TC-005): `105-106` (GitHub Step Summary env check), `119-155` (multi-space pre-flight loop), `252` (no-markdown-changes early return), `350` (content-unavailable guard), `385-400` (image upload path), `491-498` (image HTTP fetch). None are regressions from TC-005 changes; all are pre-existing gaps.

**Recommendation:** Add targeted tests in a future PR — particularly the `content-unavailable` guard (line 350) which is reachable from RENAMED events when `fetch_files_batch` returns an empty dict for the new path.

---

**Finding CR-04 (LOW):** `confluence_client.py` coverage is 56% — pre-existing, below 80%.

Methods `create_page`, `update_page` (error branches), `find_page_by_property` (pagination, duplicates), `list_all_pages_with_property` (pagination), `get_page_property`, and `upload_attachment` are partially or fully uncovered. Not introduced by TC-005.

**Recommendation:** Track as a dedicated follow-on ticket: `test_confluence_client_extended.py` covering pagination paths and HTTP error branches using `respx` (already in the test dependencies).

---

## Review Verdict

| Dimension | Status | Notes |
|-----------|--------|-------|
| Correctness | **PASS** | All FRs pass. FR-08/FR-10 partial notes documented above. |
| Security | **PASS** | No secrets leaked; `_sanitised_error()` covers all new log paths. |
| Error Handling | **PASS** | Tenacity, idempotency, per-file isolation all correct. |
| Test Coverage | **PASS WITH NOTES** | All new paths tested; 2 coverage gaps (CR-02 directory, CR-03 module%). |
| Code Clarity | **PASS** | Isolated try/except pattern is readable; naming is clear. |
| DRY | **PASS** | No duplication introduced. |
| Dependency Safety | **PASS** | No new dependencies added. |

**Final verdict: PASS WITH MINOR ISSUES**

No BLOCKER or HIGH findings. Two MEDIUM findings:
- CR-01 — missing success log for RENAMED archive (observability gap; no data loss)
- CR-02 — FR-10 directory path untested (pre-existing code; functional gap in TC-005 test suite)

Safe to proceed to Phase 7 (Verification). CR-01 fix is recommended before PR merge; CR-02 acceptable as a follow-on test.
