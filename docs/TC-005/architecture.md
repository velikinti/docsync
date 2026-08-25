# Architecture — Archive Confluence Pages on Source File Deletion

**Test Case:** TC-005
**Phase:** 2 — Architecture
**Depends on:** docs/TC-005/requirements.md (Phase 1, APPROVED)

---

## 1. System Overview

DocSync is a Python CLI that syncs GitHub Markdown files to Confluence Cloud on every push to
`main`. The deletion-archiving feature extends the existing `SyncEngine` pipeline: when the
GitHub Commits API reports a file as `removed` (or `renamed`), DocSync locates the
corresponding Confluence page via the `docsync:source_path` content property and moves it to
the Confluence trash — preserving recoverability while eliminating stale pages.

The implementation is **additive and minimal**: three targeted changes are required across two
existing modules (`config.py`, `sync.py`). No new files, no new external dependencies, and no
changes to `ConfluenceClient`, `GitHubClient`, `HierarchyManager`, or the CLI entry point.
The `archive_page()` DELETE endpoint, `find_page_by_property()` lookup, and
`HierarchyManager.archive_directory()` recursive archiver are already production-ready.

A new `archive_on_delete: bool` config flag (default `true`) gives teams an opt-out escape
hatch without breaking existing `.docsync.yml` files. A single `log.warning` call for
missing pages closes the silent-skip observability gap. `ChangeType.RENAMED` handling is added
to `_process_file()` so that rename events archive the old path before upserting the new one.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitHub Actions CI                           │
│  push to main ──► docsync sync --sha $GITHUB_SHA --owner ... --repo │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ CLI (click)
                               ▼
                    ┌─────────────────────┐
                    │      main.py        │  load .env + .docsync.yml
                    │   (CLI entry point) │  construct GitHubClient,
                    └────────┬────────────┘  ConfluenceClient, SyncEngine
                             │
                             ▼
                    ┌─────────────────────┐
                    │     SyncEngine      │  orchestrates the full pipeline
                    │      sync.py        │◄── DocSyncConfig (pydantic)
                    └──┬──────────────┬───┘
                       │              │
              [list_changed_files]  [process each file]
                       │              │
                       ▼              ▼
            ┌──────────────┐   ┌─────────────────────────────────────┐
            │ GitHubClient │   │         _process_file()             │
            │ github_      │   │                                     │
            │ client.py    │   │  DELETED ──► _handle_delete()       │
            └──────────────┘   │  RENAMED ──► _handle_rename()  NEW  │
              GitHub REST API  │  ADDED   ──► _handle_upsert()       │
                               │  MODIFIED ► _handle_upsert()       │
                               └──────┬──────────────────────────────┘
                                      │
                          ┌───────────▼──────────────┐
                          │    ConfluenceClient       │
                          │    confluence_client.py   │
                          │                           │
                          │  find_page_by_property()  │──► Confluence REST API v2
                          │  archive_page()  (@retry) │    (page DELETE endpoint)
                          │  create_page()            │
                          │  update_page()            │
                          └──────────┬────────────────┘
                                     │ (directory-type pages only)
                          ┌──────────▼────────────────┐
                          │    HierarchyManager        │
                          │    hierarchy.py            │
                          │                            │
                          │  archive_directory()       │──► recursive child archive
                          └────────────────────────────┘
```

---

## 2. Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Python 3.10+ | Existing stack; `match`/structural pattern matching available if needed |
| HTTP client | `httpx` (sync in ConfluenceClient, async in GitHubClient) | Already in use; supports both sync and async contexts |
| Config parsing | `pydantic v2` `BaseModel` | Schema validation + default values; `archive_on_delete` adds one field |
| Retry logic | `tenacity` `@_RETRY` decorator | Declarative; already applied to all `ConfluenceClient` mutating methods |
| CLI | `click` | Existing; no new flags required for this feature |
| Logging | `structlog` JSON renderer | Structured key=value log lines; `log.warning()` for missing pages |
| Testing | `pytest` + `unittest.mock` | Mock `ConfluenceClient` and `GitHubClient`; no real HTTP in unit tests |
| CI/CD | GitHub Actions | `GITHUB_SHA`, `GITHUB_STEP_SUMMARY` env vars already wired |

---

## 3. Component Responsibilities

### 3.1 `src/docsync/config.py` — Configuration Model

**Change:** Add one field to `DocSyncConfig`.

| Item | Detail |
|------|--------|
| File | `src/docsync/config.py` |
| Purpose | Parse and validate `.docsync.yml`; expose typed config to SyncEngine |
| New field | `archive_on_delete: bool = Field(default=True, description="Archive Confluence pages when source files are deleted")` |
| Backward compatibility | Pydantic `default=True` means existing `.docsync.yml` files need no changes |
| Dependencies | `pydantic v2`, `yaml`, `os.environ` |

```python
# Signature change only — one new field
class DocSyncConfig(BaseModel):
    ...
    archive_on_delete: bool = Field(default=True, description="Archive Confluence pages when source files are deleted")
```

---

### 3.2 `src/docsync/sync.py` — Sync Engine

**Changes:** `_handle_delete()` gets two additions; `_process_file()` gets a RENAMED branch.

| Item | Detail |
|------|--------|
| File | `src/docsync/sync.py` |
| Purpose | Orchestrate diff → filter → fetch → upsert/archive pipeline |

#### `_handle_delete(path, space_key, hierarchy)` — two additions

```python
async def _handle_delete(
    self, path: str, space_key: str,
    hierarchy: Optional[HierarchyManager] = None,
) -> SyncResult:
    if self._cfg.dry_run:
        return SyncResult(path=path, status=SyncStatus.SKIPPED,
                          space_key=space_key, error="dry-run")

    # NEW — FR-07: respect archive_on_delete flag
    if not self._cfg.archive_on_delete:
        log.debug("archive_on_delete_disabled", path=path)
        return SyncResult(path=path, status=SyncStatus.SKIPPED,
                          space_key=space_key, error="archive_on_delete=false")

    existing_id = self._cf.find_page_by_property(
        space_key, "docsync:source_path", path
    )
    if not existing_id:
        # NEW — FR-06: emit structured warning instead of silent skip
        log.warning("page_not_found_for_delete", path=path, space_key=space_key)
        return SyncResult(path=path, status=SyncStatus.SKIPPED,
                          space_key=space_key, error="Page not found in Confluence")

    path_type = self._cf.get_page_property(existing_id, "docsync:path_type") or "file"
    # ... rest unchanged
```

#### `_process_file(changed, contents, space_key, hierarchy)` — RENAMED branch

```python
async def _process_file(self, changed: ChangedFile, ...) -> SyncResult:
    path = changed.path
    try:
        if changed.change_type == ChangeType.DELETED:
            return await self._handle_delete(path, space_key, hierarchy)

        # NEW — FR-08: treat rename as archive-old + upsert-new (DD-TC005-03)
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

        raw = contents.get(path)
        ...
        return await self._handle_upsert(path, raw, space_key, hierarchy)
    except Exception as exc:
        ...
```

---

### 3.3 `src/docsync/confluence_client.py` — Confluence Client *(no changes)*

| Method | Relevance |
|--------|-----------|
| `find_page_by_property(space_key, "docsync:source_path", path)` | Locates page for deleted path (FR-03) |
| `archive_page(page_id)` | Calls `DELETE /wiki/rest/api/content/{id}`; 404 → silent no-op (NFR-04); decorated with `@_RETRY` (NFR-01) |
| `get_page_property(page_id, "docsync:path_type")` | Determines file vs directory for archiving strategy (FR-10) |
| `get_child_page_ids(page_id)` | Used by `HierarchyManager.archive_directory()` (FR-10) |

---

### 3.4 `src/docsync/github_client.py` — GitHub Client *(no changes)*

`list_changed_files()` already maps GitHub `status: "removed"` → `ChangeType.DELETED` and
`status: "renamed"` → `ChangeType.RENAMED` with `previous_path` populated. No changes needed.

---

### 3.5 `src/docsync/hierarchy.py` — Hierarchy Manager *(no changes)*

`archive_directory(dir_path)` already handles recursive archiving with BFS + semaphore
throttling + depth limit. Fully satisfies FR-10.

> **Deferred optimization (GAP-03):** `_handle_delete` calls `ConfluenceClient.find_page_by_property()`
> directly, bypassing `HierarchyManager._page_id_cache` built by `prefetch_page_cache()`. For
> large spaces this results in O(P) page scans per deletion. This is a pre-existing gap shared
> by all delete operations. A follow-on ticket should add a `HierarchyManager.lookup_page_id()`
> public method and thread it through `_handle_delete`.

---

## 4. Data Flow

The following steps describe the complete path from a GitHub push event to Confluence pages
being archived.

```
 1. Developer pushes to `main`; GitHub Actions sets GITHUB_SHA.

 2. GitHub Actions runs:
      docsync sync --sha $GITHUB_SHA --owner acme --repo docs-repo

 3. main.py:
      a. Loads .env (dotenv) — CONFLUENCE_API_TOKEN, CONFLUENCE_USER, GITHUB_TOKEN
      b. Loads .docsync.yml via load_config() → DocSyncConfig (pydantic validation)
         * archive_on_delete defaults to true if absent from YAML
      c. Constructs GitHubClient, ConfluenceClient, SpaceRouter, SyncEngine

 4. SyncEngine.run() → _run_async():
      a. Resolves active Confluence spaces from config
      b. Pre-flight: checks space access (can_write) for multi-space configs
      c. Builds HierarchyManager per active space; prefetches page cache

 5. GitHubClient.list_changed_files(owner, repo, sha):
      GET /repos/{owner}/{repo}/commits/{sha}
      Maps status:"removed" → ChangeType.DELETED
      Maps status:"renamed" → ChangeType.RENAMED (previous_path populated)

 6. _matches_globs() filters the changed file list (include_globs / exclude_globs).

 7. GitHub file content is fetched only for non-DELETED paths
    (fetch_files_batch skips DELETED entries — no wasted API calls).

 8. For each filtered ChangedFile:

    [DELETED path]
      a. _handle_delete(path, space_key, hierarchy)
         i.  dry_run? → SKIPPED (no Confluence calls)
         ii. archive_on_delete=false? → SKIPPED + log.debug
         iii. find_page_by_property("docsync:source_path", path)
              → None? log.warning("page_not_found_for_delete") → SKIPPED
              → found: page_id
         iv. get_page_property(page_id, "docsync:path_type")
              → "directory": hierarchy.archive_directory(path) → recursive archive
              → "file" (default): archive_page(page_id) → DELETE endpoint
                * 404 response → idempotent no-op
                * 5xx → tenacity retries ×3 with exp back-off → RuntimeError → FAILED

    [RENAMED path]
      a. _handle_delete(previous_path, ...) — same flow as above for the old page
      b. _handle_upsert(path, raw, ...) — creates/updates the new page

    [ADDED / MODIFIED path]
      a. _handle_upsert(path, raw, ...) — unchanged existing flow

 9. SyncResult appended to SyncReport with SyncStatus.ARCHIVED / SKIPPED / FAILED.

10. SyncReport.log_jsonlines() — structured JSON per file to stdout.
    SyncReport.write_github_step_summary() — Markdown table to $GITHUB_STEP_SUMMARY.
    _print_summary() — human-readable totals including archived_count.

11. sys.exit(1) if any SyncStatus.FAILED results.
```

---

## 5. Directory Layout

Only files with `(CHANGE)` or `(NEW)` are affected. All others are unchanged.

```
src/docsync/
├── config.py              (CHANGE) Add archive_on_delete: bool = True
├── sync.py                (CHANGE) _handle_delete: + warning + archive_on_delete check
│                                   _process_file: + RENAMED branch
├── confluence_client.py   (no change)
├── github_client.py       (no change)
├── hierarchy.py           (no change)
├── space_router.py        (no change)
├── main.py                (no change)
├── converter.py           (no change)
└── __init__.py            (no change)

tests/
├── test_sync_delete.py    (NEW)    Unit tests: deletion, missing-page warning,
│                                  archive_on_delete=false, dry-run, renamed handling
├── test_config.py         (CHANGE) Add test for archive_on_delete field default + override
└── (existing test files)  (no change)

docs/
└── TC-005/
    ├── requirements.md    (Phase 1 output)
    └── architecture.md    (this document)
```

---

## 6. Security Architecture

| Concern | Mechanism |
|---------|-----------|
| `CONFLUENCE_API_TOKEN` | Read from `os.environ["CONFLUENCE_API_TOKEN"]` only; never in YAML, logs, or code |
| `CONFLUENCE_USER` | Read from `os.environ["CONFLUENCE_USER"]` only |
| `GITHUB_TOKEN` | Read from `os.environ.get("GITHUB_TOKEN", "")` only |
| HTTP auth headers | `_sanitised_headers()` redacts `Authorization: Bearer ***` before any log call |
| Confluence error bodies | `_sanitised_error()` truncates response text to 200 chars; never logs raw bodies |
| `archive_page()` logging | Logs only `page_id` (an integer) — no content, no user data, no tokens |
| `page_not_found_for_delete` warning | Logs `path` and `space_key` only — both are safe repository file paths |
| `.docsync.yml` | `archive_on_delete` is a boolean; no secret values in config file |

No new attack surface is introduced. The DELETE endpoint is already in use; the new code
paths reuse the same `_sanitised_error()` / `@_RETRY` / env-var patterns.

---

## 7. Error Handling Strategy

| Scenario | Component | Behaviour |
|----------|-----------|-----------|
| `archive_on_delete: false` in config | `_handle_delete` | `log.debug("archive_on_delete_disabled")` → `SyncStatus.SKIPPED` |
| `dry_run: true` | `_handle_delete` | No Confluence calls → `SyncStatus.SKIPPED` (`error="dry-run"`) |
| Deleted file has no Confluence page | `_handle_delete` | `log.warning("page_not_found_for_delete", path, space_key)` → `SyncStatus.SKIPPED` |
| Confluence DELETE returns 404 | `archive_page()` | Silent no-op — idempotent (page already absent); no retry triggered |
| Confluence API 5xx during archive | `archive_page()` + tenacity | Retry ×3, exponential back-off (2 s → 30 s); re-raises `RuntimeError` → `SyncStatus.FAILED` |
| Renamed file — old page not in Confluence | `_handle_delete(previous_path)` | `log.warning("page_not_found_for_delete")` → SKIPPED; upsert of new path proceeds normally |
| Renamed file — content unavailable for new path | `_handle_upsert` | `SyncStatus.SKIPPED` (`error="Content unavailable"`) — existing behaviour |
| Directory page not found in Confluence | `archive_directory()` | `log.info("no_page_for_directory_skip")` → empty list → `SyncStatus.SKIPPED` |
| Archive depth limit exceeded | `_collect_descendants()` | `log.warning("archive_depth_limit_reached", depth, max_depth)` → subtree truncated |
| Glob filter excludes deleted file | `_matches_globs()` | File never reaches `_handle_delete`; not present in `SyncReport` |
| GitHub Commits API error | `list_changed_files()` | Raises `RuntimeError` → CLI catches → `sys.exit(1)` |
| Config validation failure | `load_config()` / pydantic | Raises `ValueError` → CLI catches → `sys.exit(1)` |
| `continue_on_error=True` + FAILED space | `_run_async()` | Logs warning, skips space; does not raise; non-zero exit still if any file FAILs |
| RENAMED archive fails after all retries | `_process_file` | `log.warning("rename_archive_failed", previous_path, error)` → upsert of new path proceeds; old page remains in Confluence (stale but recoverable) |
| RENAMED `previous_path` outside `include_globs` | `_run_async` / `_matches_globs` | File excluded entirely; old Confluence page not archived; deferred edge case (DD-TC005-05) |

---

## 8. Requirement Traceability

| ID | Requirement Summary | Component | Mechanism | Status |
|----|---------------------|-----------|-----------|--------|
| FR-01 | Detect `ChangeType.DELETED` from GitHub API | `GitHubClient` | `list_changed_files()` maps `status:"removed"` | **Exists** |
| FR-02 | Apply glob filters to deleted paths | `SyncEngine` | `_matches_globs()` applied before `_process_file` | **Exists** |
| FR-03 | Locate page by `docsync:source_path` | `ConfluenceClient` | `find_page_by_property()` | **Exists** |
| FR-04 | Archive page via DELETE endpoint | `ConfluenceClient` | `archive_page()` | **Exists** |
| FR-05 | Record `SyncStatus.ARCHIVED` in `SyncReport` | `SyncReport` | `archived_count`, `summary_dict()` | **Exists** ¹ |
| FR-06 | Warn when page not found | `SyncEngine._handle_delete` | Add `log.warning("page_not_found_for_delete")` | **NEW** |
| FR-07 | `archive_on_delete` config flag | `DocSyncConfig` + `_handle_delete` | New pydantic field; early return in `_handle_delete` | **NEW** |
| FR-08 | Handle `ChangeType.RENAMED` | `SyncEngine._process_file` | New branch: archive `previous_path` + upsert `path` | **NEW** |
| FR-09 | Skip archiving in dry-run mode | `SyncEngine._handle_delete` | Existing `if self._cfg.dry_run` guard | **Exists** |
| FR-10 | Recursive directory archiving | `HierarchyManager` | `archive_directory()` → `_collect_descendants()` | **Exists** |
| FR-11 | `archived_count` in report & step summary | `SyncReport` | `archived_count`, `write_github_step_summary()` | **Exists** |
| NFR-01 | 3× retry with exp back-off on `archive_page` | `ConfluenceClient` | `@_RETRY` decorator already applied | **Exists** |
| NFR-02 | Archive ≤ 10 s per attempt | `ConfluenceClient` + httpx | `timeout=30` on `_client()`; Confluence SLA < 500 ms | **Exists** |
| NFR-03 | No secrets in delete-path logs | `ConfluenceClient` | `_sanitised_error()` on all HTTP errors | **Exists** |
| NFR-04 | Idempotent on 404 | `ConfluenceClient.archive_page` | `if status_code == 404: return` | **Exists** |
| NFR-05 | Total overhead ≤ N × 1 s | `SyncEngine._run_async` | Sequential per-file loop; Confluence latency ≤ 500 ms | **Exists** |

¹ **FR-05 caveat (DD-TC005-02):** For `ChangeType.RENAMED` events, the archive of
`previous_path` is **not** added to `SyncReport` as a separate `SyncResult` — only the
upsert of the new path is. The archive is observable via `log.info("rename_archived_previous")`
or `log.warning("rename_archive_failed")` in structlog output. Changing `_process_file` to
return `List[SyncResult]` is deferred to a future refactor.

**Net gaps: 0.** All 11 FRs and 5 NFRs are fully covered. Three items require new code
(FR-06, FR-07, FR-08); the remaining twelve are satisfied by the existing implementation.
