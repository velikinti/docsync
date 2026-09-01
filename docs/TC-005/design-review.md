# Design Review — Archive Confluence Pages on Source File Deletion

**Test Case:** TC-005
**Phase:** 3 — Design Review
**Reviewer mindset:** Assume the architecture has problems. Find them before code is written.
**Input:** docs/TC-005/architecture.md (Phase 2, APPROVED)

---

## Risk Analysis

### RISK-01 — MEDIUM: RENAMED archive exception prevents upsert and misattributes error

**Condition:** `_handle_delete(previous_path)` exhausts all tenacity retries and raises
`RuntimeError`. This happens when Confluence returns 5xx on the DELETE for the old page.

**What goes wrong:** The proposed pseudocode falls through from `_handle_delete` to
`_handle_upsert` in sequence. If `_handle_delete` raises, the outer `except Exception as exc`
block fires and returns `SyncResult(path=NEW_path, status=FAILED, error=str(exc))`. Two
consequences:
1. `_handle_upsert` never runs — the renamed file is never created in Confluence. The docs
   are now out of sync with no page at the new path.
2. The error is attributed to the **new path** in `SyncReport`, even though the failure was
   on the **old path** archive. An operator reading the report cannot tell what actually broke.

**Mitigation / Required Action:** Wrap the RENAMED archive call in its own isolated
`try/except` inside `_process_file`. A failure to archive `previous_path` SHALL be logged at
WARNING level and then the upsert of the new path SHALL proceed unconditionally:

```python
if changed.change_type == ChangeType.RENAMED and changed.previous_path:
    try:
        await self._handle_delete(changed.previous_path, space_key, hierarchy)
    except Exception as exc:
        log.warning(
            "rename_archive_failed",
            previous_path=changed.previous_path,
            error=str(exc),
        )
    # always fall through to upsert regardless of archive outcome
```

**Architecture update:** Section 3.2 pseudocode updated. Section 7 error table updated.
**Design Decision:** DD-TC005-03

---

### RISK-02 — MEDIUM: `_handle_delete` bypasses `HierarchyManager` prefetch cache

**Condition:** Any commit that deletes N files where the Confluence space has thousands of
pages.

**What goes wrong:** `HierarchyManager.prefetch_page_cache()` is called once at startup and
builds `_page_id_cache: Dict[source_path, page_id]` from a single bulk API call. But
`_handle_delete` calls `self._cf.find_page_by_property()` directly, executing a full
paginated O(P) scan (P = total pages in space) for each deleted file. For a space with 5 000
pages and a commit deleting 20 files, this fetches up to 100 000 pages worth of data
unnecessarily.

**Root cause:** Pre-existing architecture gap (not introduced by TC-005). The `hierarchy`
parameter is passed to `_handle_delete` but only used for directory-type archiving, not for
the initial lookup.

**Mitigation:** DEFERRED to a follow-on ticket. The cache bypass is pre-existing behavior
shared by all delete operations; fixing it requires adding a `lookup_page_id(source_path)` 
public method to `HierarchyManager` and threading it through `_handle_delete` — a clean but
broader change than this PR's scope. This TC-005 implementation does not worsen the existing
behavior; it adds no additional unbounded scans beyond what was already happening.

**Architecture update:** Section 3.5 note added. Section 7 table note added.

---

### RISK-03 — LOW: RENAMED `previous_path` archive result is invisible in `SyncReport`

**Condition:** Every RENAMED file event in a push.

**What goes wrong:** `_process_file` returns a single `SyncResult` for the renamed file — the
upsert result for the **new path**. The archive outcome for `previous_path` is never appended
to `SyncReport`. Consequences:
- `SyncReport.archived_count` does not count pages archived due to renames.
- `write_github_step_summary()` does not mention the old page disappearing.
- An operator debugging a missing page will see no trace of the archive in DocSync output.

**Mitigation:** The archive of `previous_path` SHALL be logged with
`log.info("rename_archived_previous", previous_path=..., page_id=...)` on success and
`log.warning("rename_archive_failed", ...)` on failure. The SyncReport omission is accepted
as a design constraint (DD-TC005-02): changing `_process_file` to return `List[SyncResult]`
is a larger refactor outside this PR's scope. Operators can query structlog output for the full
picture.

**Architecture update:** Section 3.2 and FR-05 traceability row clarified.

---

### RISK-04 — LOW: Confluence rate limiting under bulk deletion commits

**Condition:** A commit deletes 50+ Markdown files (e.g., a repository restructure).

**What goes wrong:** Each deletion requires up to 3 sequential Confluence API calls:
`find_page_by_property` (paginated) + `get_page_property` + `archive_page`. Confluence Cloud
rate-limits at ~300 req/min. 50 deletions × 3 calls = 150 calls; 500 deletions × 3 = 1500
calls (~5 min). GitHub Actions jobs time out at 6 hours by default, so catastrophic failure
is unlikely, but large commits will be noticeably slow.

**Mitigation:** Accepted; consistent with NFR-05 and the existing sequential processing
model. The `asyncio.Semaphore(batch_size)` pattern already used in `HierarchyManager` and
`GitHubClient` could be extended to Confluence operations in a future performance pass
(outside TC-005 scope). No action for this PR.

---

### RISK-05 — LOW: `previous_path` not in `_matches_globs` filter for RENAMED events

**Condition:** A file is renamed from a path matching `include_globs` to one that does not
(or vice versa).

**What goes wrong (partial):** In `_run_async`, the glob filter is applied to `f.path` (the
**new** path) for all change types including RENAMED. If the **new** path does not match
`include_globs`, the file is excluded entirely and neither archive nor upsert runs — which is
correct. However, if the **old** path matched `include_globs` but the **new** path does not,
the old Confluence page is never archived, leaving a stale page.

**Mitigation:** Accepted for TC-005 scope. The requirement FR-02 only specifies applying glob
filters to deleted file paths. A rename where the new path is outside the include globs is an
edge case best handled in a future PR alongside broader glob-filter refinements. Log note
added to architecture.

---

## Gap Analysis

### GAP-01: FR-05 traceability for RENAMED events needs explicit documentation

**Missing:** The architecture's traceability table says FR-05 is "Exists" without noting that
RENAMED archive results are not in `SyncReport`. This understates the gap and could mislead
an implementer.

**Resolution:** Traceability row for FR-05 updated in architecture.md (this phase).

---

### GAP-02: Test matrix for RENAMED + dry_run combination not explicit

**Missing:** The directory layout lists `test_sync_delete.py` with "renamed handling" but
does not call out the `RENAMED + dry_run=True` combination specifically. In dry-run mode,
the `_handle_delete(previous_path)` call returns SKIPPED immediately; the upsert also returns
SKIPPED. The SyncReport has one SKIPPED entry for the new path. The old path archive is
invisible. This is the correct behavior, but it needs an explicit test to verify.

**Resolution:** Phase 4 (Impl Planning) adds this to the test plan. Phase 7 (Verification)
verifies it.

---

### GAP-03: `HierarchyManager` cache exposure method not designed

**Missing:** For RISK-02 mitigation to be implemented in a future ticket, `HierarchyManager`
needs a `lookup_page_id(source_path: str) -> Optional[str]` public method that checks the
prefetch cache before falling back to the live API. This interface is not yet designed.

**Resolution:** Deferred to a follow-on ticket. Not blocking TC-005.

---

## Design Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| DD-TC005-01 | `archive_on_delete` defaults to `true` | Preserves existing behavior — current code already archives deletions. Existing `.docsync.yml` files need no changes. |
| DD-TC005-02 | RENAMED: SyncReport records only the upsert of the new path; archive of old path is logged only | `_process_file` returns a single `SyncResult`. Changing to `List[SyncResult]` is a broader refactor outside this PR's scope. |
| DD-TC005-03 | RENAMED archive wrapped in isolated try/except; upsert always proceeds | Prevents an archive failure from blocking creation of the new page. Avoids misattribution of errors in SyncReport. (Resolves RISK-01) |
| DD-TC005-04 | `find_page_by_property` cache bypass deferred | Pre-existing gap; fixing requires `HierarchyManager.lookup_page_id()` API addition — out of scope for TC-005. (See GAP-03, RISK-02) |
| DD-TC005-05 | Glob filter applied to new path only for RENAMED events | FR-02 specifies filtering on deleted paths. Cross-glob rename edge case deferred to a future PR. (See RISK-05) |

---

## Architecture Updates Applied

The following changes have been made directly to `docs/TC-005/architecture.md`:

1. **Section 3.2** — `_process_file` RENAMED pseudocode updated to wrap archive in
   `try/except` (RISK-01 / DD-TC005-03).
2. **Section 3.5** — Added note that `_handle_delete` bypasses `HierarchyManager` cache;
   deferred to GAP-03.
3. **Section 7** — Added two rows: `RENAMED archive fails after retries` and
   `RENAMED previous_path outside include_globs`.
4. **Section 8** — FR-05 traceability row annotated with DD-TC005-02 caveat about RENAMED.

---

## Review Verdict

| Dimension | Status | Notes |
|-----------|--------|-------|
| Functional Completeness | **PASS** | All 11 FRs covered. RENAMED reporting gap documented (DD-TC005-02). |
| Security | **PASS** | No new attack surface. `_sanitised_error()` covers all new code paths. |
| Performance | **PASS WITH NOTE** | Cache bypass is pre-existing, not worsened. Bulk-delete slowness accepted per NFR-05. |
| Reliability | **PASS** | RISK-01 resolved by DD-TC005-03 (isolated try/except). Retry + idempotency in place. |
| Idempotency | **PASS** | 404 on DELETE → no-op. Duplicate archive runs safely. |
| Testability | **PASS** | All dependencies mockable. RENAMED + dry_run test case added to plan (GAP-02). |

**Overall verdict: PASS — no unresolved HIGH risks. Safe to proceed to Phase 4.**
