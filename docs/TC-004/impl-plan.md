# Implementation Plan — TC-004: Nested Directory Structure as Parent-Child Confluence Pages

**Derived from:** docs/TC-004/architecture.md + docs/TC-004/design-review.md
**Date:** 2026-08-06

---

## Scope Summary

US-004 adds the `HierarchyManager` component and extends `ConfluenceClient`, `SyncEngine`, and `DocSyncConfig`. All existing public interfaces are backward-compatible. Tasks are ordered dependency-first; every implementation task is paired with a test task.

---

## Migration Note (DD-TC004-07)
Pages synced by pre-US-004 code do not have a `docsync:source_path` property. A migration script is **out of scope** for this implementation — document in README that spaces synced before US-004 should be cleared or manually back-filled. Implementation will not attempt to repair legacy pages.

---

## Task List

| Task ID | Description | File(s) | Depends On | Priority | Est. |
|---------|-------------|---------|------------|----------|------|
| T-01 | Add `space_root_page_ids: Dict[str, str] = {}` field and `root_page_ids` computed property to `DocSyncConfig` | `config.py` | — | P0 | 20 min |
| T-02 | Write unit tests for `DocSyncConfig.root_page_ids` (single space, multi-space, global fallback, missing both) | `tests/test_config.py` | T-01 | P1 | 20 min |
| T-03 | Add `get_child_page_ids(page_id)` async method to `ConfluenceClient` (API: GET `/wiki/api/v2/pages/{id}/children`) | `confluence_client.py` | — | P0 | 30 min |
| T-04 | Add `find_page_by_property(space_key, property_key, property_value)` async method to `ConfluenceClient`; sort multi-match by `last_modified_at` desc; log WARNING for duplicates (DD-TC004-06) | `confluence_client.py` | — | P0 | 40 min |
| T-05 | Add `list_all_pages_with_property(space_key, property_key)` async method to `ConfluenceClient`; return `{property_value: page_id}` dict (DD-TC004-03) | `confluence_client.py` | — | P0 | 40 min |
| T-06 | Extend `create_page` in `ConfluenceClient` to accept optional `path_type: str = "file"` and set `docsync:path_type` custom property on the created page (DD-TC004-02) | `confluence_client.py` | T-03 | P0 | 30 min |
| T-07 | Write unit tests for `get_child_page_ids`, `find_page_by_property` (single match, multi-match dedup, no match), `list_all_pages_with_property`, extended `create_page` with `path_type` | `tests/test_confluence_client.py` | T-03, T-04, T-05, T-06 | P1 | 60 min |
| T-08 | Create `src/docsync/hierarchy.py` — `AncestorChain` dataclass + `HierarchyManager.__init__` with `_page_id_cache`, `_creation_locks`, `_semaphore`, `max_archive_depth` | `hierarchy.py` | T-03, T-04, T-05, T-06 | P0 | 30 min |
| T-09 | Implement `HierarchyManager.prefetch_page_cache()` — calls `list_all_pages_with_property("docsync:source_path")`, pre-fills `_page_id_cache` (DD-TC004-03) | `hierarchy.py` | T-08 | P0 | 25 min |
| T-10 | Implement `HierarchyManager._ensure_directory_page(dir_path, parent_page_id, segment)` — asyncio.Lock per dir_path, cache-then-create, sets `path_type="directory"` (DD-TC004-01, DD-TC004-02, DD-TC004-05) | `hierarchy.py` | T-09 | P0 | 45 min |
| T-11 | Implement `HierarchyManager.resolve_parent_id(file_path)` — iterates `PurePosixPath(file_path).parts[:-1]`, calls `_ensure_directory_page` per segment, returns leaf parent_id | `hierarchy.py` | T-10 | P0 | 35 min |
| T-12 | Implement `HierarchyManager._collect_descendants(page_id, depth)` — BFS via `get_child_page_ids`; stop at `max_archive_depth`, log WARNING (DD-TC004-04) | `hierarchy.py` | T-11 | P0 | 30 min |
| T-13 | Implement `HierarchyManager.archive_directory(dir_path)` — looks up root page by `find_page_by_property("docsync:source_path", dir_path)`, calls `_collect_descendants`, archives each via `archive_page` with semaphore (DD-TC004-04) | `hierarchy.py` | T-12 | P0 | 35 min |
| T-14 | Write unit tests for `HierarchyManager`: prefetch, single-level parent resolution, 3-level deep chain, concurrent `_ensure_directory_page` (lock prevents duplicates), `archive_directory` BFS, `max_archive_depth` guard, dry-run synthetic IDs | `tests/test_hierarchy.py` (new file) | T-13 | P1 | 90 min |
| T-15 | Update `SyncEngine._run_async`: instantiate one `HierarchyManager` per active space; call `prefetch_page_cache()` per space after pre-flight; pass `hierarchy` into `_process_file` | `sync.py` | T-13 | P0 | 35 min |
| T-16 | Update `SyncEngine._process_file`: call `hierarchy.resolve_parent_id(file.path)` to get `parent_page_id`; use `parent_page_id` in `create_page` / `update_page`; set `path_type="file"` on create | `sync.py` | T-15 | P0 | 40 min |
| T-17 | Update `SyncEngine._run_async` delete dispatch: query `docsync:path_type` property (via `find_page_by_property`) to distinguish file vs directory; call `hierarchy.archive_directory()` for directories; `archive_page()` for files (DD-TC004-02) | `sync.py` | T-16 | P0 | 40 min |
| T-18 | Write unit tests for updated `SyncEngine`: nested file create (2-level, 3-level), file update with existing parent, file delete (archive single), directory delete (archive_directory called), `--dry-run` no writes, `--spaces` filter skips other-space files | `tests/test_sync.py` | T-17 | P1 | 90 min |
| T-19 | Write integration-level tests for `SyncEngine` + `HierarchyManager` together (mock ConfluenceClient + GitHubClient): full path from `docs/api/v2/auth.md` creates 3 parent pages + 1 file page in correct order | `tests/test_sync_spaces.py` | T-18 | P1 | 60 min |
| T-20 | Update `conftest.py`: add `mock_hierarchy_manager` fixture + pre-populated `page_property_map` fixture | `tests/conftest.py` | T-14 | P0 | 20 min |
| T-21 | Update `__init__.py` to export `HierarchyManager` from `docsync.hierarchy` | `__init__.py` | T-08 | P0 | 5 min |

---

## Dependency Graph

```
T-01 ──────────────────────────────────────────────────────► T-02 (test)
T-03 ──┐
T-04 ──┤
T-05 ──┤──► T-06 ──► T-07 (test)
           │
           └──► T-08 ──► T-09 ──► T-10 ──► T-11 ──► T-12 ──► T-13 ──► T-14 (test)
                │                                                      │
                └──► T-21                                              ▼
                                                               T-15 ──► T-16 ──► T-17 ──► T-18 (test)
                                                               │                           │
                                                               T-20 (fixture)              ▼
                                                                                  T-19 (integration test)
```

**Critical path:** T-03/T-04/T-05 → T-06 → T-08 → T-09 → T-10 → T-11 → T-12 → T-13 → T-15 → T-16 → T-17 → T-18 → T-19

---

## Blocking Relationships

| Blocked Task | Blocked By | Why |
|-------------|------------|-----|
| T-06 | T-03 | `create_page` needs `get_child_page_ids` to exist to verify child creation in tests |
| T-08 | T-03, T-04, T-05, T-06 | `HierarchyManager.__init__` takes a `ConfluenceClient` — all four new methods must exist before the manager can be constructed |
| T-09 | T-08 | `prefetch_page_cache` calls `self._confluence.list_all_pages_with_property` — T-05 must exist |
| T-10 | T-09 | `_ensure_directory_page` reads from `_page_id_cache` (populated by T-09) and calls `create_page` with `path_type` (T-06) |
| T-11 | T-10 | `resolve_parent_id` calls `_ensure_directory_page` for each segment |
| T-12 | T-11 | `_collect_descendants` calls `self._confluence.get_child_page_ids` (T-03) and is called by `archive_directory` |
| T-13 | T-12 | `archive_directory` calls `_collect_descendants` (T-12) and `find_page_by_property` (T-04) |
| T-14 | T-13 | Tests exercise the full `HierarchyManager` surface |
| T-15 | T-13 | `SyncEngine` instantiates `HierarchyManager` — all methods must be implemented |
| T-16 | T-15 | `_process_file` calls `hierarchy.resolve_parent_id` (T-11) |
| T-17 | T-16 | Delete dispatch calls `hierarchy.archive_directory` (T-13) and `find_page_by_property` (T-04) |
| T-18 | T-17 | Tests drive the complete updated `SyncEngine` surface |
| T-19 | T-18 | Integration tests compose `SyncEngine` + `HierarchyManager` — all units must be complete |
| T-20 | T-14 | Fixtures use the `HierarchyManager` API |

---

## Task Details

### T-01 — `DocSyncConfig.space_root_page_ids` and `root_page_ids` property

In `config.py`, add to `DocSyncConfig`:
```python
space_root_page_ids: Dict[str, str] = {}

@property
def root_page_ids(self) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for sk in (self.space_keys or []):
        result[sk] = self.space_root_page_ids.get(sk) or self.root_page_id or ""
    return result
```
YAML example:
```yaml
space_root_page_ids:
  DOCS: "123456"
  ENG: "789012"
```
If only `root_page_id` is set (legacy), all active spaces fall back to it.

---

### T-03 — `ConfluenceClient.get_child_page_ids`

```python
@retry(...)
async def get_child_page_ids(self, page_id: str) -> list[str]:
    resp = await self._get(f"/wiki/api/v2/pages/{page_id}/children",
                            params={"limit": 250})
    return [p["id"] for p in resp.get("results", [])]
```
Handles pagination: follow `resp["_links"].get("next")` until exhausted.

---

### T-04 — `ConfluenceClient.find_page_by_property`

```python
@retry(...)
async def find_page_by_property(
    self, space_key: str, property_key: str, property_value: str
) -> Optional[str]:
    resp = await self._get("/wiki/api/v2/pages", params={
        "spaceKey": space_key,
        "metadata.properties.key": property_key,
        "metadata.properties.value": property_value,
        "limit": 50,
    })
    results = resp.get("results", [])
    if not results:
        return None
    if len(results) > 1:
        log.warning("duplicate_source_path_pages",
                    property_value=property_value,
                    page_ids=[r["id"] for r in results])
        results.sort(key=lambda r: r.get("version", {}).get("createdAt", ""), reverse=True)
    return results[0]["id"]
```

---

### T-05 — `ConfluenceClient.list_all_pages_with_property`

```python
@retry(...)
async def list_all_pages_with_property(
    self, space_key: str, property_key: str
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    url = "/wiki/api/v2/pages"
    params = {"spaceKey": space_key, "metadata.properties.key": property_key, "limit": 250}
    while url:
        resp = await self._get(url, params=params)
        for page in resp.get("results", []):
            for prop in page.get("metadata", {}).get("properties", {}).get("results", []):
                if prop["key"] == property_key:
                    mapping[prop["value"]] = page["id"]
        url = resp.get("_links", {}).get("next")
        params = {}  # next URL already includes params
    return mapping
```

---

### T-06 — Extend `ConfluenceClient.create_page` with `path_type`

Add optional `path_type: str = "file"` parameter. After page creation, set two custom properties:
- `docsync:source_path` = `source_path` (existing)
- `docsync:path_type` = `path_type` (new)

Property API: `POST /wiki/api/v2/pages/{id}/properties`

---

### T-08 — `HierarchyManager.__init__`

```python
import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional
import structlog
from docsync.confluence_client import ConfluenceClient

log = structlog.get_logger()

@dataclass
class AncestorChain:
    entries: list[tuple[str, str]]  # [(dir_path, page_id), ...]
    @property
    def leaf_parent_id(self) -> str:
        return self.entries[-1][1] if self.entries else ""

class HierarchyManager:
    def __init__(
        self,
        confluence: ConfluenceClient,
        space_key: str,
        root_page_id: str,
        dry_run: bool = False,
        max_archive_depth: int = 50,
        batch_size: int = 5,
    ) -> None:
        self._confluence = confluence
        self._space_key = space_key
        self._root_page_id = root_page_id
        self._dry_run = dry_run
        self._max_archive_depth = max_archive_depth
        self._page_id_cache: dict[str, str] = {}
        self._creation_locks: dict[str, asyncio.Lock] = {}
        self._semaphore = asyncio.Semaphore(batch_size)
```

---

### T-10 — `HierarchyManager._ensure_directory_page` (DD-TC004-01, DD-TC004-02, DD-TC004-05)

```python
async def _ensure_directory_page(
    self, dir_path: str, parent_page_id: str, segment: str
) -> str:
    if dir_path not in self._creation_locks:
        self._creation_locks[dir_path] = asyncio.Lock()
    async with self._creation_locks[dir_path]:
        if dir_path in self._page_id_cache:
            return self._page_id_cache[dir_path]
        if self._dry_run:
            digest = hashlib.sha256(dir_path.encode()).hexdigest()[:8]
            synthetic = f"dry-run-{digest}"
            self._page_id_cache[dir_path] = synthetic
            log.info("dry_run_intermediate_page", dir_path=dir_path, synthetic_id=synthetic)
            return synthetic
        page_id = await self._confluence.find_page_by_property(
            self._space_key, "docsync:source_path", dir_path
        )
        if not page_id:
            page_id = await self._confluence.create_page(
                space_key=self._space_key,
                title=segment,
                parent_id=parent_page_id,
                body="",
                source_path=dir_path,
                path_type="directory",
            )
        self._page_id_cache[dir_path] = page_id
        return page_id
```

---

### T-11 — `HierarchyManager.resolve_parent_id`

```python
async def resolve_parent_id(self, file_path: str) -> str:
    parts = PurePosixPath(file_path).parts[:-1]  # drop filename
    if not parts:
        return self._root_page_id
    current_parent = self._root_page_id
    accumulated = ""
    for segment in parts:
        accumulated = f"{accumulated}/{segment}".lstrip("/")
        current_parent = await self._ensure_directory_page(
            accumulated, current_parent, segment
        )
    return current_parent
```

---

### T-12 — `HierarchyManager._collect_descendants`

```python
async def _collect_descendants(self, page_id: str, depth: int = 0) -> list[str]:
    if depth >= self._max_archive_depth:
        log.warning("archive_depth_limit_reached", page_id=page_id, depth=depth)
        return []
    child_ids = await self._confluence.get_child_page_ids(page_id)
    all_descendants = list(child_ids)
    for child_id in child_ids:
        all_descendants.extend(
            await self._collect_descendants(child_id, depth + 1)
        )
    return all_descendants
```

---

### T-13 — `HierarchyManager.archive_directory`

```python
async def archive_directory(self, dir_path: str) -> list[str]:
    root_page_id = await self._confluence.find_page_by_property(
        self._space_key, "docsync:source_path", dir_path
    )
    if not root_page_id:
        log.info("no_page_for_directory_skip", dir_path=dir_path)
        return []
    descendants = await self._collect_descendants(root_page_id)
    all_ids = [root_page_id] + descendants
    archived: list[str] = []
    for page_id in all_ids:
        async with self._semaphore:
            if not self._dry_run:
                await self._confluence.archive_page(page_id)
            log.info("archived_page", page_id=page_id, dry_run=self._dry_run)
            archived.append(page_id)
    return archived
```

---

### T-15 — Update `SyncEngine._run_async` (HierarchyManager integration)

1. After pre-flight checks, build `hierarchy_map`:
```python
from docsync.hierarchy import HierarchyManager
hierarchy_map = {
    sk: HierarchyManager(
        confluence=self._confluence,
        space_key=sk,
        root_page_id=self._config.root_page_ids.get(sk, ""),
        dry_run=self._dry_run,
        batch_size=self._config.batch_size,
    )
    for sk in active_spaces
}
for hm in hierarchy_map.values():
    await hm.prefetch_page_cache()
```
2. Pass `hierarchy=hierarchy_map[resolved_space]` to each `_process_file` call.

---

### T-16 — Update `SyncEngine._process_file` (parent resolution)

```python
# Before create_page / update_page:
parent_page_id = await hierarchy.resolve_parent_id(file.path)

# On create:
page_id = await self._confluence.create_page(
    ..., parent_id=parent_page_id, path_type="file"
)
# On update — update parent if it changed:
await self._confluence.update_page(..., parent_id=parent_page_id)
```

---

### T-17 — Update `SyncEngine._run_async` delete dispatch (DD-TC004-02)

```python
if file.status == "removed":
    path_type = await self._confluence.find_page_by_property(
        resolved_space, "docsync:path_type", file.path
    )
    if path_type == "directory":
        archived_ids = await hierarchy.archive_directory(file.path)
        for pid in archived_ids:
            results.append(SyncResult(path=file.path, status=SyncStatus.ARCHIVED,
                                       space_key=resolved_space, page_id=pid))
    else:
        page_id = await self._confluence.find_page_by_property(
            resolved_space, "docsync:source_path", file.path
        )
        if page_id:
            await self._confluence.archive_page(page_id)
            results.append(SyncResult(path=file.path, status=SyncStatus.ARCHIVED,
                                       space_key=resolved_space, page_id=page_id))
```

---

## Test Coverage Plan

| Test File | Tests |
|-----------|-------|
| `tests/test_config.py` | `root_page_ids` with `space_root_page_ids`; global fallback; missing both raises |
| `tests/test_confluence_client.py` | `get_child_page_ids` (paginated); `find_page_by_property` (0, 1, 2+ results); `list_all_pages_with_property`; `create_page` sets both custom properties |
| `tests/test_hierarchy.py` (NEW) | `prefetch_page_cache` populates cache; single-level parent; 3-level chain; concurrent `_ensure_directory_page` (lock); `archive_directory` BFS; `max_archive_depth` guard; dry-run synthetic IDs |
| `tests/test_sync.py` | Nested file create; file update with parent; file delete (single); directory delete; `--dry-run` no writes; `--spaces` filter |
| `tests/test_sync_spaces.py` | `docs/api/v2/auth.md` → 3 parent pages + 1 file page; correct Confluence parent-child chain |
| `tests/conftest.py` | `mock_hierarchy_manager` fixture; `page_property_map` fixture |

---

## Estimated Timeline

| Priority | Tasks | Total Est. |
|----------|-------|-----------|
| P0 (critical path) | T-01, T-03–T-06, T-08–T-13, T-15–T-17, T-20–T-21 | ~6.5 hours |
| P1 (tests) | T-02, T-07, T-14, T-18, T-19 | ~5.5 hours |
| **Total** | | **~12 hours** |
