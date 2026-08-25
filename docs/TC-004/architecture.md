# Architecture — TC-004: Nested Directory Structure as Parent-Child Confluence Pages

## Overview

US-004 extends the `docsync sync` pipeline to faithfully mirror the GitHub repository's directory hierarchy as a tree of nested parent-child Confluence pages. Rather than creating every page as a flat sibling under the space root, the sync engine now:

1. **Resolves the full ancestor chain** for every markdown file before creating or updating it.
2. **Ensures each directory segment has a corresponding Confluence parent page** (creating an empty placeholder if none exists).
3. **Recursively archives** all descendant Confluence pages whenever a directory is removed from the repository.

The feature builds on the existing five-component architecture (GitHubClient, MarkdownConverter, ConfluenceClient, SyncEngine, CLI) and the space-routing layer introduced in US-002. A new `HierarchyManager` component is the sole addition; all other components receive targeted method additions. No existing public interfaces are broken.

---

## 1. System Overview

### ASCII Component Diagram

```
GitHub API
    │ push to main
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLI  main.py                                                   │
│  docsync sync --spaces ENG --dry-run --output-format table      │
│       │                                                         │
│       ├─ DocSyncConfig (config.py)  ←  .docsync.yml            │
│       │    • space_key / space_keys / space_mappings            │
│       │    • root_page_id (per-space)                           │
│       │    • batch_size, log_file                               │
│       │                                                         │
│       └─ SyncEngine.run()  (sync.py)                            │
│              │                                                  │
│    ┌─────────┴──────────────────────────┐                       │
│    │                                    │                       │
│  GitHubClient           HierarchyManager (hierarchy.py)  NEW   │
│  (github_client.py)       • build_ancestor_chain(path)          │
│  • list_changed_files()   • ensure_page_exists(segment, parent) │
│  • fetch_file_content()   • resolve_parent_id(path, space_key)  │
│  • fetch_file_bytes()     • archive_directory(dir_path)         │
│                           │                                     │
│                      ConfluenceClient (confluence_client.py)    │
│                        • find_page_by_property(path)            │
│                        • create_page(...)                       │
│                        • update_page(...)                       │
│                        • archive_page(page_id)                  │
│                        • get_child_page_ids(page_id)            │
│                        • upload_attachment(...)                 │
│                        • check_space_access(space_key)          │
│                                                                 │
│                      MarkdownConverter (converter.py)           │
│                        • convert(markdown_text) → xhtml         │
│                        • extract_images(markdown_text)          │
│                                                                 │
│                      SpaceRouter (space_router.py)              │
│                        • resolve(path) → space_key              │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
    Confluence Cloud
    (REST API v2)

Outputs:
  • JSON-lines log file (structlog)
  • GitHub Actions step summary
  • stdout sync summary table / JSON
```

---

## 2. Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Language | Python 3.10+ | Existing project baseline; `match` statement useful for status dispatch |
| HTTP client | `httpx` (async) | Already in use; supports HTTP/2, connection pooling, async context managers |
| Retry / back-off | `tenacity` | Declarative retry; `retry_if_exception_type`, `wait_exponential`, `stop_after_attempt` |
| Config parsing & validation | `pydantic v2` | Fail-fast startup validation; nested models for per-space `root_page_id` |
| CLI framework | `click` | Already in use; `--spaces`, `--dry-run`, `--output-format` flags already defined |
| Markdown → XHTML | `markdown2` + `lxml` | Already in use; XHTML validation and fallback macro (DD-03) |
| Structured logging | `structlog` JSON-lines | Already in use; every file operation logged as JSON line |
| Test framework | `pytest` + `pytest-asyncio` | Already in use; `unittest.mock.AsyncMock` for Confluence/GitHub stubs |
| CI/CD | GitHub Actions | Push to `main` trigger; step summary via `GITHUB_STEP_SUMMARY` |
| Path hierarchy | Python `pathlib.PurePosixPath` | OS-agnostic path manipulation; `.parts` gives directory segments |

---

## 3. Component Responsibilities

### 3.1 `HierarchyManager` — `src/docsync/hierarchy.py` *(NEW)*

**Single responsibility:** Own all logic for resolving, creating, and archiving the Confluence page tree that mirrors the repository directory structure.

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional
import structlog

from docsync.confluence_client import ConfluenceClient

log = structlog.get_logger()

@dataclass
class AncestorChain:
    """Ordered list of (segment_path, confluence_page_id) pairs, root first."""
    entries: list[tuple[str, str]]  # [(dir_path, page_id), ...]

    @property
    def leaf_parent_id(self) -> str:
        """The page_id that a leaf file should be created under."""
        return self.entries[-1][1] if self.entries else ""


class HierarchyManager:
    def __init__(
        self,
        confluence: ConfluenceClient,
        space_key: str,
        root_page_id: str,
        dry_run: bool = False,
        max_archive_depth: int = 50,
    ) -> None:
        # _page_id_cache: dir_path -> confluence_page_id (pre-filled by prefetch_page_cache)
        self._page_id_cache: dict[str, str] = {}
        # _creation_locks: dir_path -> asyncio.Lock (DD-TC004-01)
        self._creation_locks: dict[str, asyncio.Lock] = {}
        ...

    async def prefetch_page_cache(self) -> None:
        """Fetch all pages with docsync:source_path in one batch; pre-fill _page_id_cache.
        Called once per space after pre-flight checks. (DD-TC004-03)"""
        ...

    async def resolve_parent_id(
        self, file_path: str
    ) -> str:
        """Return the Confluence page ID that `file_path` should be a child of.
        Creates intermediate directory pages as needed (unless dry_run)."""
        ...

    async def _ensure_directory_page(
        self,
        dir_path: str,        # e.g. "docs/api"
        parent_page_id: str,
        segment: str,         # e.g. "api"
    ) -> str:
        """Find or create a directory placeholder page; return its page_id.
        Uses asyncio.Lock keyed on dir_path to prevent concurrent duplicate creation (DD-TC004-01).
        Sets docsync:path_type='directory' on the created page (DD-TC004-02).
        Dry-run returns synthetic ID 'dry-run-{hex8}' where hex8=sha256(dir_path)[:8] (DD-TC004-05)."""
        if dir_path not in self._creation_locks:
            self._creation_locks[dir_path] = asyncio.Lock()
        async with self._creation_locks[dir_path]:
            if dir_path in self._page_id_cache:
                return self._page_id_cache[dir_path]
            # ... create page, set docsync:path_type='directory' ...
            self._page_id_cache[dir_path] = page_id
            return page_id

    async def archive_directory(
        self,
        dir_path: str,        # e.g. "docs/api"
    ) -> list[str]:
        """Recursively archive all Confluence pages under dir_path.
        Uses asyncio.Semaphore(batch_size) for throttled API calls.
        Stops at max_archive_depth to prevent runaway recursion (DD-TC004-04).
        Returns list of archived page_ids."""
        ...

    async def _collect_descendants(
        self, page_id: str, depth: int = 0
    ) -> list[str]:
        """BFS/DFS over Confluence child pages; return all descendant page_ids.
        Stops and logs warning when depth >= max_archive_depth (DD-TC004-04)."""
        ...
```

**Dependencies:** `ConfluenceClient`, `structlog`, `asyncio`

**Design decisions applied:**
- DD-TC004-01: `asyncio.Lock` per `dir_path` in `_ensure_directory_page`
- DD-TC004-02: `docsync:path_type` property (`"file"` or `"directory"`) set on every created page
- DD-TC004-03: `prefetch_page_cache()` pre-fills cache at startup via batch API call
- DD-TC004-04: `max_archive_depth` guard + semaphore in `archive_directory`
- DD-TC004-05: Dry-run IDs use `"dry-run-{sha256(dir_path)[:8]}"` format

---

### 3.2 `ConfluenceClient` — `src/docsync/confluence_client.py` *(extended)*

Existing client; three new methods added:

```python
async def get_child_page_ids(self, page_id: str) -> list[str]:
    """Return immediate child page IDs for the given parent page_id."""
    ...

async def find_page_by_property(
    self,
    space_key: str,
    property_key: str,   # "docsync:source_path"
    property_value: str, # e.g. "docs/api"
) -> Optional[str]:
    """Return page_id if a page with the given custom property exists; else None.
    If multiple matches, sort by last_modified_at desc and return most recent;
    log WARNING with all duplicate page_ids (DD-TC004-06)."""
    ...

async def list_all_pages_with_property(
    self,
    space_key: str,
    property_key: str,   # "docsync:source_path"
) -> dict[str, str]:
    """Return {property_value: page_id} for all pages in space_key that have the property.
    Used by HierarchyManager.prefetch_page_cache() (DD-TC004-03)."""
    ...
```

**`docsync:path_type` property (DD-TC004-02):**
- `create_page` accepts an optional `path_type: str = "file"` parameter.
- `HierarchyManager._ensure_directory_page` calls `create_page(..., path_type="directory")`.
- On delete, `SyncEngine` calls `find_page_by_property("docsync:path_type", path)` to determine dispatch (archive single page vs. archive_directory).

Existing methods remain unchanged (`find_page`, `create_page`, `update_page`, `archive_page`, `upload_attachment`, `check_space_access`).

---

### 3.3 `SyncEngine` — `src/docsync/sync.py` *(extended)*

Updated `_process_file` flow:

```python
async def _process_file(
    self,
    file: ChangedFile,
    space_key: str,
    contents: bytes,
    hierarchy: HierarchyManager,   # NEW parameter
) -> SyncResult: ...
```

Updated `_run_async` flow (additions only):

```python
# Build one HierarchyManager per active space_key
hierarchy_map: dict[str, HierarchyManager] = {
    sk: HierarchyManager(self._confluence, sk, root_page_id, self._dry_run)
    for sk, root_page_id in self._config.root_page_ids.items()
    if sk in active_spaces
}

# For each deleted file whose path is a directory: archive descendants
for deleted_dir in deleted_directories:
    hierarchy = hierarchy_map[resolved_space]
    archived_ids = await hierarchy.archive_directory(deleted_dir)
    for pid in archived_ids:
        results.append(SyncResult(path=deleted_dir, status=SyncStatus.ARCHIVED,
                                   space_key=resolved_space, page_id=pid))
```

---

### 3.4 `DocSyncConfig` — `src/docsync/config.py` *(extended)*

New field: per-space `root_page_id` lookup.

```python
# Existing (unchanged)
root_page_id: Optional[str] = None   # global default

# New
space_root_page_ids: Dict[str, str] = {}
# e.g. {"DOCS": "123456", "ENG": "789012"}
# Falls back to root_page_id if space_key not in map

@property
def root_page_ids(self) -> Dict[str, str]:
    """Return effective root_page_id per active space key."""
    result = {}
    for sk in (self.space_keys or []):
        result[sk] = self.space_root_page_ids.get(sk, self.root_page_id or "")
    return result
```

---

### 3.5 `CLI` — `src/docsync/main.py` *(unchanged)*

No new flags required for US-004. Existing `--spaces`, `--dry-run`, `--output-format` flags from US-002/US-003 cover all NFRs.

---

## 4. Data Flow

```
 1. GitHub push to `main` triggers GitHub Actions workflow
 2. CLI `docsync sync` starts; loads `.docsync.yml` into DocSyncConfig
 3. SyncEngine.run() called; pre-flight checks all active space keys (US-002)
 4. GitHubClient.list_changed_files(owner, repo, sha) → list[ChangedFile]
    - ChangedFile.status ∈ {added, modified, removed}
 5. For each active space, instantiate HierarchyManager(confluence, space_key, root_page_id)
 6. For each ChangedFile:
    a. SpaceRouter.resolve(file.path) → space_key (or SKIP if no mapping)
    b. If space_key not in active_spaces → SyncResult(SKIPPED)
    c. If file.status == "removed":
       - Check if it's a directory (no extension) → HierarchyManager.archive_directory(path)
       - Otherwise → ConfluenceClient.archive_page(find_page_by_property(path))
    d. Otherwise (added / modified):
       - HierarchyManager.resolve_parent_id(file.path) → parent_page_id
         └── For each ancestor dir segment:
               i. ConfluenceClient.find_page_by_property("docsync:source_path", dir_path)
              ii. If not found: ConfluenceClient.create_page(title=segment, parent=parent_id, body="")
             iii. Cache result in HierarchyManager._page_id_cache[dir_path]
       - GitHubClient.fetch_file_content(path) → markdown_text
       - MarkdownConverter.convert(markdown_text) → xhtml
       - MarkdownConverter.extract_images(markdown_text) → list[ImageRef]
       - For each ImageRef:
           GitHubClient.fetch_file_bytes(image_path) → bytes
           ConfluenceClient.upload_attachment(page_id, filename, bytes)
           rewrite image src in xhtml to attachment URL
       - existing_page_id = ConfluenceClient.find_page_by_property("docsync:source_path", file.path)
       - if existing_page_id → update_page(existing_page_id, xhtml, parent_page_id)
       - else → create_page(title, parent_page_id, xhtml, space_key, source_path=file.path)
    e. Emit JSON-lines log entry (structlog)
    f. Append SyncResult to SyncReport
 7. SyncEngine emits elapsed time into SyncReport (US-003)
 8. CLI calls _print_summary(report, dry_run, output_format)
 9. CLI exits 0 (no errors) or 1 (any FAILED)
```

---

## 5. Directory Layout

```
src/docsync/
  __init__.py
  config.py              ← add space_root_page_ids, root_page_ids property
  confluence_client.py   ← add get_child_page_ids(), find_page_by_property()
  converter.py           ← no change
  github_client.py       ← no change
  hierarchy.py           ← NEW: HierarchyManager
  main.py                ← no change (flags from US-002/003 already sufficient)
  space_router.py        ← no change
  sync.py                ← pass HierarchyManager into _process_file; handle dir archives

tests/
  conftest.py            ← add HierarchyManager fixtures
  test_hierarchy.py      ← NEW: unit tests for HierarchyManager
  test_config.py         ← add tests for root_page_ids property
  test_confluence_client.py  ← add tests for get_child_page_ids, find_page_by_property
  test_sync.py           ← add tests for nested path processing + dir archive
  test_sync_spaces.py    ← no change
  test_sync_summary.py   ← no change
  test_converter.py      ← no change
  test_github_client.py  ← no change
  test_space_router.py   ← no change
```

---

## 6. Security Architecture

| Concern | Mechanism |
|---------|-----------|
| Confluence API token | `CONFLUENCE_API_TOKEN` env var only; never in `.docsync.yml`, logs, or page bodies |
| GitHub token | `GITHUB_TOKEN` env var only |
| structlog redaction | Fields named `*token*`, `*password*`, `*secret*` auto-redacted by `structlog` processor |
| HTTP exception sanitisation | `ConfluenceClient` strips `Authorization` header value from all exception context before re-raising (DD-05) |
| Page body | Confluence pages never contain raw file paths with credential fragments |
| `.docsync.yml` | Contains only base URLs, space keys, page IDs — safe to commit |
| `docsync:source_path` values | Contain only repo-relative file paths — no secrets |

---

## 7. Error Handling Strategy

| Scenario | Behaviour |
|----------|-----------|
| Confluence API returns HTTP 429 / 5xx | Retry up to 3× with exponential back-off (base 1 s, max 30 s) via `tenacity`; mark `SyncResult(FAILED)` after exhausted retries |
| Intermediate parent page creation fails | Propagate exception; mark the leaf file as `FAILED`; do not leave orphan pages |
| `find_page_by_property` returns multiple matches | Log warning, use first result (most recent creation); idempotent on re-run |
| Directory deletion with no Confluence page | Log info ("no page found for dir_path, skip archive"); no error |
| `resolve_parent_id` cycle detected (malformed path) | Raise `ValueError` immediately; mark file `FAILED` |
| Image fetch from GitHub fails (404) | Log warning; continue page creation/update without the image; do not fail page |
| `--dry-run` mode | All `HierarchyManager` write operations return a synthetic placeholder page_id (`"dry-run-<hash>"`); no network writes |
| Config missing `root_page_id` for space | Fall back to global `root_page_id`; if neither set, raise `ValueError` at startup |
| Space key not found in Confluence (pre-flight) | Fail entire run (exit 1) unless `--continue-on-error` passed (US-002 behaviour unchanged) |
| `lxml` XHTML validation failure | Fall back to Confluence code-block macro for that page (DD-03); log warning |

---

## 8. Requirement Traceability

| Requirement | Component / Mechanism |
|-------------|----------------------|
| FR-001 — unlimited nesting | `HierarchyManager.resolve_parent_id()` walks `PurePosixPath.parts` to any depth |
| FR-002 — intermediate placeholder pages | `HierarchyManager._ensure_directory_page()` creates empty pages per segment |
| FR-003 — root_page_id anchor | `DocSyncConfig.root_page_ids` per-space mapping |
| FR-004 — identity by `docsync:source_path` | `ConfluenceClient.find_page_by_property()` |
| FR-005 — create on new file | `SyncEngine._process_file()` → `create_page` |
| FR-006 — update on changed file | `SyncEngine._process_file()` → `update_page` |
| FR-007 — archive on file delete | `ConfluenceClient.archive_page()` via `SyncEngine` |
| FR-008 — recursive archive on dir delete | `HierarchyManager.archive_directory()` + `_collect_descendants()` |
| FR-009 — archive + create on file move | Detected as remove+add pair; archive old path, create new with new parent |
| FR-010 — inline image upload | `MarkdownConverter.extract_images()` + `ConfluenceClient.upload_attachment()` |
| FR-011 — JSON-lines log | `structlog` JSON renderer; one log call per file operation |
| FR-012 — retry on 429/5xx | `tenacity` `@retry` decorator on all `ConfluenceClient` mutating methods |
| FR-013 — `--dry-run` | `HierarchyManager(dry_run=True)` returns synthetic IDs; no Confluence writes |
| FR-014 — `--spaces` filtering | `SpaceRouter` + `active_spaces` check (US-002 unchanged) |
| FR-015 — sync summary | `SyncReport.summary_dict()` + `_print_summary()` (US-003 unchanged) |
| FR-016 — configurable `root_page_id` | `DocSyncConfig.space_root_page_ids` + `root_page_ids` property |
| NFR-001 — 500 files ≤ 60 s | Async `asyncio.Semaphore(batch_size)` for concurrent Confluence calls |
| NFR-002 — idempotency | `HierarchyManager._page_id_cache` + `find_page_by_property` prevents duplicate pages |
| NFR-003 — retry back-off | `tenacity` wait_exponential(min=1, max=30) |
| NFR-004 — valid JSON-lines | `structlog` JSONRenderer; each entry terminated by `\n` only |
| NFR-005 — no credential leakage | structlog redaction + HTTP exception sanitisation |
| NFR-006 — testability | All clients injected via constructor; `HierarchyManager` accepts mock `ConfluenceClient` |
| NFR-007 — backward compat | `root_page_id` global fallback preserved |
| NFR-008 — depth correctness | `PurePosixPath(file.path).parts` drives segment iteration |
