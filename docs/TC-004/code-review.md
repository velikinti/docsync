# Code Review — TC-004: Nested Directory Structure as Parent-Child Confluence Pages

**Reviewer:** Senior Peer Reviewer (phase-6-code-review)
**Files reviewed:** `src/docsync/hierarchy.py`, `src/docsync/confluence_client.py` (new methods), `src/docsync/config.py`, `src/docsync/sync.py`, `tests/test_hierarchy.py`
**Test run:** 117 passed, 0 failed
**Coverage:** 80% overall (hierarchy.py 99%, confluence_client.py 61%, sync.py 76%)
**Date:** 2026-08-06

---

## Overall Assessment

The implementation is well-structured and follows the architecture faithfully. The critical design decisions (DD-TC004-01 through DD-TC004-05) are implemented. However, there are two HIGH severity issues that must be fixed before this can be merged — a non-paginated `find_page_by_property` that silently truncates results, and a directory-delete dispatch logic that never actually calls `archive_directory`. Several MEDIUM issues improve correctness and coverage.

---

## 1. Correctness (Requirement Traceability)

| FR | Status | Evidence |
|----|--------|----------|
| FR-001 — unlimited nesting | ✅ PASS | `resolve_parent_id` iterates `PurePosixPath.parts[:-1]` with no depth cap |
| FR-002 — intermediate placeholder pages | ✅ PASS | `_ensure_directory_page` creates page with `body=""` per segment |
| FR-003 — root_page_id anchor | ✅ PASS | `HierarchyManager.__init__` accepts `root_page_id`; `resolve_parent_id` starts from it |
| FR-004 — identity by `docsync:source_path` | ✅ PASS | `find_page_by_property("docsync:source_path", path)` is canonical lookup |
| FR-005 — create on new file | ✅ PASS | `_handle_upsert` → `create_page` with `path_type="file"` and resolved `parent_id` |
| FR-006 — update on changed file | ✅ PASS | `_handle_upsert` → `update_page` when `find_page` returns existing |
| FR-007 — archive on file delete | ⚠️ PARTIAL | `_handle_delete` reaches `find_page` + `archive_page` for files, but see ISSUE-02 |
| FR-008 — recursive archive on dir delete | ❌ FAIL | See ISSUE-02 — `archive_directory` is never called in practice |
| FR-009 — archive+create on file move | ✅ PASS | Move is detected as DELETED+ADDED pair; handled by existing archive+create flow |
| FR-010 — inline image upload | ✅ PASS | `_handle_upsert` calls `upload_attachment` for each extracted image |
| FR-011 — JSON-lines log | ✅ PASS | `structlog` call per file in `_run_async` + `archive_directory` |
| FR-012 — retry on 429/5xx | ✅ PASS | `@_RETRY` on all `ConfluenceClient` mutating methods |
| FR-013 — `--dry-run` no writes | ✅ PASS | `_handle_upsert`/`_handle_delete` both return SKIPPED early when `cfg.dry_run` |
| FR-014 — `--spaces` filtering | ✅ PASS | `SpaceRouter` + `active_spaces` check (US-002 unchanged) |
| FR-015 — sync summary | ✅ PASS | `SyncReport.summary_dict()` + `_print_summary()` (US-003 unchanged) |
| FR-016 — configurable root_page_id | ✅ PASS | `DocSyncConfig.space_root_page_ids` + `root_page_ids` property |

---

## 2. Findings

---

### ISSUE-01 — HIGH: `find_page_by_property` does not paginate — silently truncates results on large spaces

**File:** `src/docsync/confluence_client.py`, lines ~270-298

**Problem:** The method fetches exactly one page of results from `/wiki/rest/api/content` with no `limit` parameter and no pagination loop. In a space with >25 pages (the Confluence default page size), any page beyond the first 25 results will never be found by this method. This causes `_ensure_directory_page` to see a "not found" cache miss even for pages that exist, resulting in duplicate intermediate pages being created until the next `prefetch_page_cache` run.

`list_all_pages_with_property` correctly paginates. `find_page_by_property` does not.

**Evidence:**
```python
# confluence_client.py ~line 278
with self._client() as client:
    resp = client.get(url, params=params)  # no limit, no pagination loop
...
for page in resp.json().get("results", []):   # only first page
```

**Fix required:**
```python
params = {
    "type": "page",
    "spaceKey": space_key,
    "expand": "version,metadata.properties",
    "limit": 250,
}
while url:
    with self._client() as client:
        resp = client.get(url, params=params)
        ...
    for page in resp.json().get("results", []):
        ...check for match...
        if found: return page_id
    url = resp.json().get("_links", {}).get("next", "")
    params = {}
return None
```

**Severity: HIGH** — Creates duplicate Confluence pages in spaces with >25 existing pages.

---

### ISSUE-02 — HIGH: Directory delete dispatch never calls `archive_directory` — FR-008 not met

**File:** `src/docsync/sync.py`, `_handle_delete` method

**Problem:** The delete dispatch logic reads `path_type_value` from `PurePosixPath(path).suffix` heuristic after computing `existing_id` via `find_page_by_property`. However, `find_page_by_property` is called with `"docsync:path_type"` and the `path` value — which is incorrect. The method signature is `find_page_by_property(space_key, property_key, property_value)`, meaning it searches for pages where property `docsync:path_type` equals the file path string (e.g. `"docs/api"`). That will never match, because `docsync:path_type` is stored as `"file"` or `"directory"`, not as a path.

As a result, `path_type_page_id` is always `None`, `path_type_value` always uses the `.suffix` fallback heuristic (which DD-TC004-02 was specifically designed to eliminate), and `archive_directory` is never called.

**Evidence:**
```python
# sync.py _handle_delete
path_type_page_id = self._cf.find_page_by_property(
    space_key, "docsync:path_type", path   # BUG: path_value is file path, not "directory"
)
...
path_type_value = "directory" if not PurePosixPath(path).suffix else "file"
# ^ This heuristic runs every time because path_type_page_id is always None
```

**Fix required:** Correct the lookup to query `docsync:source_path` to get the page_id, then query that page's `docsync:path_type` property value. Simplest fix:

```python
# Look up the page first
existing_id = self._cf.find_page_by_property(
    space_key, "docsync:source_path", path
)
if not existing_id:
    return SyncResult(path=path, status=SyncStatus.SKIPPED,
                      space_key=space_key, error="Page not found in Confluence")

# Determine path type: query docsync:path_type stored on the page
# Simpler: since we set path_type at create time, check suffix-free paths
# against our own cache or use the stored property via the content API
path_type_value = self._cf.get_page_property(existing_id, "docsync:path_type") or "file"

if path_type_value == "directory" and hierarchy is not None:
    ...
```

Alternatively, add `get_page_property(page_id, key)` to `ConfluenceClient` using `GET /wiki/rest/api/content/{id}/property/{key}`. This is the correct approach per DD-TC004-02.

**Severity: HIGH** — FR-008 (recursive directory archive) is never exercised. Deleting a directory only archives the root page, leaving all descendant pages orphaned.

---

### ISSUE-03 — MEDIUM: `_handle_delete` has dead/duplicate code paths after ISSUE-02

**File:** `src/docsync/sync.py`, lines ~457-496

**Problem:** The method computes `path_type_page_id`, `is_directory`, and `existing_id` in overlapping and redundant patterns due to multiple stale iterations of the logic. After ISSUE-02 is fixed, the method should be simplified. The current code makes 3 calls to `find_page_by_property` for a single delete operation (one for `path_type`, one for `source_path` inside `is_directory` condition, one at the end as `existing`), creating unnecessary Confluence API calls.

**Fix:** Consolidate to one `find_page_by_property("docsync:source_path", path)` call, then one `get_page_property(page_id, "docsync:path_type")` call.

**Severity: MEDIUM** — Correctness impact (ISSUE-02 parent) + performance (3× API calls per delete).

---

### ISSUE-04 — MEDIUM: `get_child_page_ids` loop sentinel uses falsy empty string — exits on first page

**File:** `src/docsync/confluence_client.py`, lines ~334-350

**Problem:** The pagination loop uses:
```python
url = f"{self._base_url}{next_link}" if next_link else ""
params = {}
while url:
```
On the second iteration, if `next_link` is absent, `url` becomes `""` (falsy), correctly exiting the loop. However the initial `url` assignment and the `while url` guard interact correctly. This is not a bug per se, but it is inconsistent with `list_all_pages_with_property` which uses the same pattern correctly. The issue is that the `url` variable is reassigned inside the `while` body by building `f"{self._base_url}{next_link}"` — but on the first iteration, `url` already starts as the full URL with `params`, and on subsequent iterations `params = {}` causes the next-page URL query string to be duplicated if the `next` link already includes query params. Confluence `_links.next` returns a relative URL that already includes all necessary query parameters, so prepending the base and passing `params={}` correctly avoids duplication. **No bug, but deserves a comment.**

**Fix:** Add a one-line comment: `# _links.next is a relative URL with all query params included; params={} on subsequent iterations`

**Severity: LOW** — Clarity only, no correctness impact.

---

### ISSUE-05 — MEDIUM: `AncestorChain` dataclass is defined but never used

**File:** `src/docsync/hierarchy.py`, line 22-27

**Problem:** `AncestorChain` is defined with `entries` and `leaf_parent_id` property but is never constructed or returned anywhere in `HierarchyManager`. `resolve_parent_id` returns a raw `str` (page_id). The dataclass is dead code.

**Evidence:** Coverage shows line 27 (`return self.entries[-1][1]`) is not covered (the one uncovered line at 99%).

**Fix:** Either remove `AncestorChain` entirely, or refactor `resolve_parent_id` to build and return an `AncestorChain` for richer callers. Given the architecture only needs the final parent page_id, removal is simpler.

**Severity: LOW** — Dead code, no functional impact. Confuses readers.

---

### ISSUE-06 — MEDIUM: `confluence_client.py` coverage 61% — three new methods untested end-to-end

**Coverage:** `get_child_page_ids`, `find_page_by_property`, `list_all_pages_with_property` all have 0% HTTP-level test coverage. Lines 238-356 are entirely uncovered.

**Missing tests needed:**
- `get_child_page_ids`: single page of children; paginated (two pages); HTTP 500 raises RuntimeError
- `find_page_by_property`: match on page 1; no match; two matches (dedup + WARNING); HTTP error
- `list_all_pages_with_property`: single page; paginated; no matching pages

**Severity: MEDIUM** — Code paths involving the Confluence REST API are untested. Bugs in pagination or property matching would not be caught.

---

### ISSUE-07 — LOW: `sync.py` coverage 76% — `_handle_upsert` hierarchy branch untested

**Coverage:** Lines 340, 375, 379-387 in `sync.py` are uncovered. Line 340 is the `parent_id = await hierarchy.resolve_parent_id(path)` branch; lines 375-387 are the `create_page` call with `path_type="file"`.

The existing `test_sync.py` tests pass `hierarchy=None` (legacy mode). No test exercises the `hierarchy is not None` path in `_handle_upsert`.

**Fix:** Add one test in `test_sync.py` that injects a mock `HierarchyManager` and verifies `resolve_parent_id` is called and its result is passed as `parent_id` to `create_page`.

**Severity: LOW** — The hierarchy-aware upsert path (the main US-004 feature) has no direct test in `test_sync.py`.

---

### ISSUE-08 — LOW: Security — `_sanitised_error` truncates response body to 200 chars but does not strip `Authorization` header echoes

**File:** `src/docsync/confluence_client.py`, `_sanitised_error`

The current implementation:
```python
return RuntimeError(
    f"Confluence API error {exc.response.status_code}: "
    f"{exc.response.text[:200]}"
)
```

Confluence error responses sometimes echo back request headers (e.g. in HTML error pages from a reverse proxy). The 200-character truncation partially mitigates this, but does not guarantee the `Authorization` header value is excluded if it appears in the first 200 characters of the response body. This is an edge case (Confluence Cloud does not typically echo auth headers), but the risk exists with custom reverse proxies.

**Recommended fix:** Strip any substring matching `Bearer [A-Za-z0-9+/=._-]+` or `Basic [A-Za-z0-9+/=]+` from `exc.response.text` before truncating.

**Severity: LOW** — Theoretical risk; Confluence Cloud does not echo auth tokens in practice.

---

## 3. Error Handling

| Scenario | Status |
|----------|--------|
| Tenacity on `create_page`, `update_page`, `archive_page` | ✅ `@_RETRY` present |
| Tenacity on `get_child_page_ids`, `find_page_by_property`, `list_all_pages_with_property` | ✅ `@_RETRY` present |
| Per-file exception isolation in `_process_file` | ✅ `try/except Exception` wraps full body |
| Image fetch failure is non-fatal | ✅ `_fetch_image` returns `None` on exception, continues |
| Directory page not found on archive | ✅ Returns `[]` with log.info |
| `max_archive_depth` exceeded | ✅ Logs WARNING, returns `[]` for that subtree |

---

## 4. Security

| Check | Status |
|-------|--------|
| No hardcoded credentials | ✅ All tokens via `os.environ` |
| structlog field names for tokens | ✅ Fields named `space_key`, `dir_path`, `page_id` — no token fields |
| HTTP exception sanitisation | ⚠️ 200-char truncation present; full auth strip not implemented (ISSUE-08, LOW) |
| `.docsync.yml` secrets | ✅ Only URLs, space keys, page IDs — safe to commit |
| `docsync:source_path` values | ✅ Repo-relative paths only |

---

## 5. Code Clarity

The `HierarchyManager` is well-commented and has clear single-responsibility methods. The `_handle_delete` method in `sync.py` is the most complex and confusing area — three overlapping `find_page_by_property` calls with inconsistent logic (ISSUE-02, ISSUE-03).

---

## 6. DRY

No new DRY violations introduced. The `@_RETRY` decorator pattern (an existing project-wide pattern) is consistently applied to all four new `ConfluenceClient` methods.

---

## 7. Dependency Safety

No new dependencies introduced by TC-004. `requirements.txt` unchanged.

---

## Required Fixes Before Merge

| # | Issue | Severity | File |
|---|-------|----------|------|
| 1 | `find_page_by_property` does not paginate — duplicate pages on large spaces | HIGH | `confluence_client.py` |
| 2 | Directory delete dispatch logic never calls `archive_directory` — FR-008 broken | HIGH | `sync.py` |
| 3 | Dead code: `AncestorChain` defined but never used | LOW | `hierarchy.py` |
| 4 | Missing HTTP-level tests for 3 new ConfluenceClient methods | MEDIUM | `test_confluence_client.py` |
| 5 | Missing test for hierarchy-aware upsert path in `_handle_upsert` | LOW | `test_sync.py` |

Issues 1 and 2 must be fixed. Issues 3-5 are required before final merge but do not block the code review sign-off.
