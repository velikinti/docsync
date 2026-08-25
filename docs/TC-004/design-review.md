# Design Review — TC-004: Nested Directory Structure as Parent-Child Confluence Pages

**Reviewer:** Senior Engineer (sdlc-design-review)
**Architecture doc:** docs/TC-004/architecture.md
**Requirements doc:** docs/TC-004/requirements.md
**Date:** 2026-08-06

---

## Review Summary

The architecture introduces `HierarchyManager` as a focused, well-scoped new component. It extends three existing components (`ConfluenceClient`, `SyncEngine`, `DocSyncConfig`) with targeted additions and leaves unchanged components untouched. Risk level overall is **MEDIUM**, primarily driven by three concerns: idempotency of in-flight hierarchy creation under concurrency, the archive-on-directory-delete relying on a path-heuristic, and the cost of `find_page_by_property` API calls at scale.

---

## Findings

### PASS — Component Isolation
`HierarchyManager` owns all hierarchy logic and depends only on `ConfluenceClient`. It does not reach into `SyncEngine` internals. Dependency injection via constructor makes it fully mockable for unit tests.

### PASS — Page Identity via `docsync:source_path`
Using a custom Confluence page property as the canonical identity (DD-01) is correct. It prevents title-collision bugs and survives page title edits in Confluence. `find_page_by_property` is the right lookup mechanism.

### PASS — Backward Compatibility
Global `root_page_id` fallback is preserved. Legacy `.docsync.yml` files continue to work unchanged (NFR-007). The `space_root_page_ids` dict is additive.

### PASS — Security Architecture
No credentials in page bodies, log entries, or `.docsync.yml`. structlog redaction covers `*token*`, `*password*`, `*secret*` field names. HTTP exception sanitisation (DD-05) is referenced. The JSON-lines summary dict contains only counts and elapsed time.

### PASS — Retry Strategy
`tenacity` exponential back-off (base 1 s, max 30 s, 3 attempts) is the existing pattern. Extending it to the two new `ConfluenceClient` methods (`get_child_page_ids`, `find_page_by_property`) is consistent.

---

## Risks

### RISK-01 — HIGH: Race condition in concurrent intermediate page creation

**Issue:** `resolve_parent_id` iterates ancestor segments and calls `_ensure_directory_page` for each. Under `asyncio.Semaphore(batch_size)` multiple coroutines may simultaneously attempt to create the same intermediate page (e.g. `docs/api` parent) because the in-process `_page_id_cache` is only populated *after* the create call returns. A second coroutine reaches the cache-miss branch before the first coroutine's create completes, resulting in duplicate Confluence pages.

**Action (required before implementation):**
Use an `asyncio.Lock` keyed on `dir_path` inside `HierarchyManager._ensure_directory_page`. The pattern:
```python
if dir_path not in self._creation_locks:
    self._creation_locks[dir_path] = asyncio.Lock()
async with self._creation_locks[dir_path]:
    if dir_path in self._page_id_cache:
        return self._page_id_cache[dir_path]
    # ... create page ...
    self._page_id_cache[dir_path] = page_id
    return page_id
```
This ensures exactly one coroutine creates each intermediate page, while all others wait and then read from cache.

**Architecture change:** Add `_creation_locks: dict[str, asyncio.Lock]` to `HierarchyManager.__init__` and document the locking pattern. **→ DONE: architecture.md updated (Section 3.1).**

---

### RISK-02 — HIGH: Directory deletion detection relies on heuristic (no file extension)

**Issue:** The data flow (Section 4, step 6c) identifies a deleted path as a directory by checking "no extension". This is fragile: files like `CHANGELOG`, `Makefile`, `LICENSE` have no extension but are files. Conversely, a directory named `v2.0` contains a dot. A GitHub `ChangedFile` with `status == "removed"` and no extension will incorrectly trigger `archive_directory` instead of `archive_page`.

**Action (required before implementation):**
GitHub's commit comparison API returns `status` per changed path but does NOT distinguish file vs. directory in the changed-files list. Instead:
- Maintain a **path registry** (`docsync:source_path` properties in Confluence) — the property already exists on every synced page. If a removed path has a matching Confluence page with property type `"file"`, archive that page. If it has type `"directory"`, recurse.
- Add a `docsync:path_type` property (value `"file"` or `"directory"`) to every page on create. `HierarchyManager._ensure_directory_page` sets `"directory"`; `SyncEngine._process_file` sets `"file"`.
- On delete, look up `docsync:path_type` to dispatch correctly.

**Architecture change:** Add `docsync:path_type` custom page property to the data model. Update `create_page` and `_ensure_directory_page` to set it. Update delete dispatch to query it. **→ DONE: architecture.md updated (Sections 3.1 and 3.2).**

---

### RISK-03 — MEDIUM: `find_page_by_property` API cost at scale

**Issue:** For a repo with 500 files at depth 5, building ancestor chains calls `find_page_by_property` up to 5× per file = 2,500 API calls before any content is synced. The Confluence Cloud REST API v2 property search endpoint has rate limits (typically 300 req/min per user). This risks HTTP 429 throttling and violates NFR-001 (500 files ≤ 60 s).

**Action (required before implementation):**
- `HierarchyManager._page_id_cache` MUST be populated eagerly at startup: call `ConfluenceClient.list_all_pages_with_property("docsync:source_path")` once per space, returning all `(source_path → page_id)` pairs, and pre-fill the cache. Subsequent `_ensure_directory_page` calls then hit the cache (no API call) for already-existing pages.
- Only new segments (cache miss) require an API call to verify absence, then one call to create.

**Architecture change:** Add `HierarchyManager.prefetch_page_cache(space_key)` method and a corresponding `ConfluenceClient.list_all_pages_with_property(space_key, property_key)` method. `SyncEngine._run_async` calls `prefetch_page_cache` once per space after pre-flight checks. **→ DONE: architecture.md updated (Sections 3.1 and 3.2).**

---

### RISK-04 — MEDIUM: Recursive archive with no depth limit can exceed Confluence API rate limits

**Issue:** `HierarchyManager._collect_descendants` does a BFS/DFS calling `get_child_page_ids` recursively. For a large deleted directory tree (e.g. 200 pages), this generates 200+ individual `archive_page` API calls in rapid succession. No throttle mechanism is described for this path.

**Action (required before implementation):**
- Wrap `archive_page` calls inside `asyncio.Semaphore(batch_size)` (the same semaphore already used for file processing).
- Add a `max_archive_depth: int = 50` config guard; log a warning and stop if exceeded, marking remaining descendants as `SKIPPED(reason="archive_depth_limit")` to prevent infinite loops on malformed Confluence page trees.

**Architecture change:** Document `max_archive_depth` config option and semaphore use in Section 3.1 error handling. **→ DONE: architecture.md updated.**

---

### RISK-05 — MEDIUM: `--dry-run` placeholder page IDs break ancestor chain resolution

**Issue:** `dry_run=True` returns synthetic IDs like `"dry-run-<hash>"` for newly created intermediate pages. If a subsequent (still dry-run) call uses that synthetic ID as the `parent_page_id` for a deeper child page, `create_page` in dry-run mode receives a fake parent ID. This is fine as long as dry-run never writes — but if the synthetic ID collides with a real Confluence page ID (numeric strings) the logged output would show incorrect parent IDs, misleading the operator.

**Action (Phase 4 — low severity, document only):**
Generate dry-run synthetic IDs as `"dry-run-{dir_path_hash}"` where `dir_path_hash` is a short hex digest of the path. These cannot collide with real Confluence numeric page IDs (which are integer strings). Document this in the dry-run section of error handling. **→ ACCEPTED: no architecture change needed.**

---

### RISK-06 — LOW: `find_page_by_property` returns multiple matches — silent first-result behaviour

**Issue:** The architecture says "log warning, use first result". If two pages share the same `docsync:source_path` property value (created due to a prior race condition or manual error), using the first silently ignores the second, which may be the more-recently-updated page. Subsequent syncs may update the wrong page.

**Action (Phase 4 — document in implementation notes):**
When multiple results are returned, sort by `last_modified_at` descending and use the most recently modified. Log all duplicate page IDs at WARNING level so operators can clean up. **→ ACCEPTED: document in impl-plan.**

---

### RISK-07 — LOW: `docsync:source_path` property not set on legacy pages (pre-US-004)

**Issue:** Pages created before US-004 (via US-001/US-002) may have been identified by title rather than `docsync:source_path`. When US-004 runs against a space that was previously synced with old code, `find_page_by_property` finds nothing, and US-004 creates duplicate pages.

**Action (Phase 5 — migration note):**
Document in the implementation plan that spaces synced with pre-US-004 code should either be cleared or have `docsync:source_path` properties back-filled via a one-time migration script. This is out of scope for US-004 but must not be silently ignored. **→ ACCEPTED: note in impl-plan.**

---

## Agreed Design Decisions

| ID | Decision |
|----|----------|
| DD-TC004-01 | `HierarchyManager._ensure_directory_page` MUST use `asyncio.Lock` keyed on `dir_path` to prevent concurrent duplicate intermediate page creation. |
| DD-TC004-02 | Add `docsync:path_type` custom Confluence page property (`"file"` or `"directory"`) to distinguish files from directories at delete time; do not rely on file extension heuristic. |
| DD-TC004-03 | `HierarchyManager.prefetch_page_cache(space_key)` pre-fills `_page_id_cache` at startup by fetching all pages with `docsync:source_path` in one batch, minimising per-file API calls. |
| DD-TC004-04 | Recursive archive uses `asyncio.Semaphore(batch_size)` and respects `max_archive_depth` (default 50) to prevent runaway API calls on deep trees. |
| DD-TC004-05 | Dry-run synthetic page IDs use format `"dry-run-{hex8}"` where `hex8` is the first 8 characters of `sha256(dir_path)`, preventing collision with real Confluence numeric page IDs. |
| DD-TC004-06 | When `find_page_by_property` returns multiple matches, sort by `last_modified_at` descending and use the most recent; log all duplicate IDs at WARNING. |
| DD-TC004-07 | Archive existing flat-synced pages (pre-US-004 without `docsync:source_path`) is out of scope; document a migration note in the implementation plan. |

---

## Architecture Sign-Off

Architecture is **CONDITIONALLY APPROVED** pending the following:

1. ✅ **RISK-01 resolved** — `asyncio.Lock` per `dir_path` added to `HierarchyManager` (DD-TC004-01)
2. ✅ **RISK-02 resolved** — `docsync:path_type` property added to data model (DD-TC004-02)
3. ✅ **RISK-03 resolved** — `prefetch_page_cache` method added (DD-TC004-03)
4. ✅ **RISK-04 resolved** — Archive semaphore + `max_archive_depth` guard added (DD-TC004-04)

All HIGH/MEDIUM items have been resolved via architecture updates above. LOW items (RISK-05 through RISK-07) are accepted as implementation notes.

Architecture is **APPROVED** for implementation planning.
