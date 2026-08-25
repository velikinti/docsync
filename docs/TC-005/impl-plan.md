# Implementation Plan — Archive Confluence Pages on Source File Deletion

**Test Case:** TC-005
**Phase:** 4 — Implementation Planning
**Input:** docs/TC-005/architecture.md + docs/TC-005/design-review.md (both APPROVED)

---

## Scope Summary

Three surgical changes across two existing files. No new modules, no new dependencies.

| File | Change Type | What Changes |
|------|-------------|--------------|
| `src/docsync/config.py` | Modify | Add `archive_on_delete: bool = Field(default=True)` |
| `src/docsync/sync.py` | Modify | `_handle_delete`: add flag check + warning log; `_process_file`: add RENAMED branch |
| `tests/test_config.py` | Modify | Add 3 tests for `archive_on_delete` field |
| `tests/test_sync_delete.py` | New file | 8 tests covering all new code paths |

---

## Task Breakdown

### Group 1 — Config Change

| Task | Description | File(s) | Depends On | Priority | Estimate |
|------|-------------|---------|------------|----------|----------|
| T-01 | Add `archive_on_delete: bool = Field(default=True, description="Archive Confluence pages when source files are deleted")` to `DocSyncConfig`. No other changes needed — pydantic default ensures backward compat with existing `.docsync.yml` files. | `src/docsync/config.py` | — | P0 | 15 min |

---

### Group 2 — Sync Engine Changes

| Task | Description | File(s) | Depends On | Priority | Estimate |
|------|-------------|---------|------------|----------|----------|
| T-02 | In `SyncEngine._handle_delete`: (1) after the `dry_run` guard, add early-return block for `not self._cfg.archive_on_delete` that calls `log.debug("archive_on_delete_disabled", path=path)` and returns `SyncStatus.SKIPPED`; (2) replace the silent `return SyncResult(..., status=SyncStatus.SKIPPED)` for missing pages with `log.warning("page_not_found_for_delete", path=path, space_key=space_key)` before the return. | `src/docsync/sync.py` | T-01 | P0 | 30 min |
| T-03 | In `SyncEngine._process_file`: add a new branch before the `contents.get(path)` fetch — check `changed.change_type == ChangeType.RENAMED and changed.previous_path`. Wrap the `await self._handle_delete(changed.previous_path, space_key, hierarchy)` call in `try/except Exception` that logs `log.warning("rename_archive_failed", previous_path=..., error=str(exc))` on failure. Fall through unconditionally to `_handle_upsert` for the new path. | `src/docsync/sync.py` | T-02 | P0 | 30 min |

---

### Group 3 — Tests

| Task | Description | File(s) | Depends On | Priority | Estimate |
|------|-------------|---------|------------|----------|----------|
| T-04 | Add `class TestArchiveOnDeleteConfig` to `tests/test_config.py` with 3 tests: `test_archive_on_delete_defaults_to_true` (omit field → `True`); `test_archive_on_delete_false_accepted` (set `False` → field is `False`); `test_archive_on_delete_true_explicit` (set `True` → field is `True`). Uses `base_config` fixture — verify existing fixture still has `archive_on_delete=True` as a regression check. | `tests/test_config.py` | T-01 | P0 | 20 min |
| T-05 | Create `tests/test_sync_delete.py` with `class TestArchiveOnDelete` (3 tests) and `class TestRenamedFileHandling` (5 tests) — full test matrix below. | `tests/test_sync_delete.py` | T-02, T-03 | P0 | 60 min |
| T-06 | Run `pytest tests/ -v --tb=short` and confirm: all pre-existing tests pass (regression), all T-04 and T-05 tests pass. No new failures. | — | T-04, T-05 | P0 | 15 min |

---

## T-05 Test Matrix (`tests/test_sync_delete.py`)

### `class TestArchiveOnDelete`

| Test | Scenario | Expected outcome |
|------|----------|-----------------|
| `test_archive_on_delete_false_skips` | Config has `archive_on_delete=False`; commit deletes `docs/old.md` | `SyncStatus.SKIPPED`; `archive_page` NOT called |
| `test_archive_on_delete_false_logs_debug` | Same as above | `structlog` captures `archive_on_delete_disabled` at DEBUG level |
| `test_page_not_found_logs_warning` | `find_page_by_property` returns `None`; commit deletes `docs/ghost.md` | `SyncStatus.SKIPPED`; `structlog` captures `page_not_found_for_delete` at WARNING level |

### `class TestRenamedFileHandling`

| Test | Scenario | Expected outcome |
|------|----------|-----------------|
| `test_renamed_archives_previous_path` | RENAMED `docs/old.md` → `docs/new.md`; page exists for `docs/old.md` | `archive_page` called with old page_id; result is CREATED or UPDATED for new path |
| `test_renamed_upserts_new_path` | RENAMED `docs/old.md` → `docs/new.md`; no existing page for new path | `create_page` called for `docs/new.md` with `path_type="file"` |
| `test_renamed_archive_failure_does_not_block_upsert` | RENAMED; `archive_page` raises `RuntimeError`; new path has no existing page | `create_page` still called; result is CREATED; `rename_archive_failed` warning logged |
| `test_renamed_dry_run_skips_archive_and_upsert` | `dry_run=True`; RENAMED `docs/old.md` → `docs/new.md` | Both archive and upsert return SKIPPED; no Confluence API calls made |
| `test_renamed_no_previous_path_skips_archive` | RENAMED with `previous_path=None` (defensive guard) | Archive skipped; upsert proceeds normally; no exception raised |

---

## Dependency Graph

```
T-01 (config.py: archive_on_delete field)
  │
  ├──► T-02 (sync.py: _handle_delete — flag check + warning)
  │      │
  │      └──► T-03 (sync.py: _process_file — RENAMED branch)
  │                 │
  │                 └──► T-05 (test_sync_delete.py — new test file)
  │                              │
  └──► T-04 (test_config.py — archive_on_delete tests)    │
              │                                            │
              └────────────────────────────────────────────┤
                                                           ▼
                                                    T-06 (pytest — full suite)

Critical path: T-01 → T-02 → T-03 → T-05 → T-06
               15 min  30 min  30 min  60 min  15 min = 150 min
```

---

## Blocked Tasks Summary

| Task | Blocked By | Reason |
|------|------------|--------|
| T-02 | T-01 | `_handle_delete` reads `self._cfg.archive_on_delete`; field must exist in `DocSyncConfig` before `SyncEngine` code references it |
| T-03 | T-02 | RENAMED branch calls `_handle_delete`; the warning log and flag check from T-02 must be in place first for T-05 tests to be consistent |
| T-04 | T-01 | Tests assert on the `archive_on_delete` field; pydantic model must have the field first |
| T-05 | T-02, T-03 | Tests verify all new behaviors from both sync changes |
| T-06 | T-04, T-05 | Regression + new test run requires all implementation and tests to be written |

---

## Implementation Notes for Phase 5

### T-02 exact insertion point in `sync.py:_handle_delete`

```python
async def _handle_delete(self, path, space_key, hierarchy=None):
    if self._cfg.dry_run:                          # ← existing
        return SyncResult(...)                     # ← existing

    # INSERT HERE — FR-07
    if not self._cfg.archive_on_delete:
        log.debug("archive_on_delete_disabled", path=path)
        return SyncResult(path=path, status=SyncStatus.SKIPPED,
                          space_key=space_key, error="archive_on_delete=false")

    existing_id = self._cf.find_page_by_property(...)  # ← existing
    if not existing_id:
        log.warning("page_not_found_for_delete",   # ← CHANGE: was silent
                    path=path, space_key=space_key)
        return SyncResult(path=path, status=SyncStatus.SKIPPED,
                          space_key=space_key, error="Page not found in Confluence")
    # ... rest unchanged
```

### T-03 exact insertion point in `sync.py:_process_file`

```python
async def _process_file(self, changed, contents, space_key, hierarchy=None):
    path = changed.path
    try:
        if changed.change_type == ChangeType.DELETED:    # ← existing
            return await self._handle_delete(path, ...)  # ← existing

        # INSERT HERE — FR-08 (DD-TC005-03: isolated try/except)
        if changed.change_type == ChangeType.RENAMED and changed.previous_path:
            try:
                await self._handle_delete(changed.previous_path, space_key, hierarchy)
            except Exception as exc:
                log.warning("rename_archive_failed",
                            previous_path=changed.previous_path, error=str(exc))
            # always fall through to upsert

        raw = contents.get(path)                         # ← existing (falls through)
        ...
```

### T-05 structlog capture pattern

Use `structlog.testing.capture_logs()` context manager to assert on logged events:

```python
from structlog.testing import capture_logs

def test_page_not_found_logs_warning(engine, mock_github, mock_confluence):
    mock_confluence.find_page_by_property.return_value = None
    mock_github.list_changed_files = AsyncMock(
        return_value=[ChangedFile(path="docs/ghost.md", change_type=ChangeType.DELETED)]
    )
    mock_github.fetch_files_batch = AsyncMock(return_value={})

    with capture_logs() as logs:
        engine.run("owner", "repo", "abc123")

    warning_events = [l for l in logs if l.get("log_level") == "warning"]
    assert any(l.get("event") == "page_not_found_for_delete" for l in warning_events)
```

---

## Effort Estimate

| Group | Tasks | Estimate |
|-------|-------|----------|
| Config change | T-01 | 15 min |
| Sync engine changes | T-02, T-03 | 60 min |
| Tests | T-04, T-05, T-06 | 95 min |
| **Total** | **6 tasks** | **170 min (~2.8 hours)** |

Critical path: **150 min** (T-01 → T-02 → T-03 → T-05 → T-06)
