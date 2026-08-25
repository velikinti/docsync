# Architecture — DocSync Automated Documentation Sync

---

## US-001 Architecture (Baseline — TC-001, COMPLETE)

*(See `outputs/TC-001/phase-2-architecture/output.md` for the full baseline architecture.)*

The existing system is a 5-component Python CLI:
- **GitHubClient** — fetches changed files from GitHub REST API
- **MarkdownConverter** — converts Markdown → Confluence Storage Format (XHTML)
- **ConfluenceClient** — CRUD operations against Confluence Cloud REST API v2
- **SyncEngine** — orchestrates the diff → convert → upsert/archive pipeline
- **CLI** (`main.py`) — click entry point; loads config and wires components

Config model: `DocSyncConfig` with a single `space_key: str` field.

---

## US-002 Architecture: `--spaces` flag  *(TC-002)*

### 1. Change Summary

US-002 adds multi-space routing to DocSync. Three categories of change:

| Category | Components affected |
|----------|---------------------|
| Config model | `config.py` — add `space_keys`, `space_mappings`; keep `space_key` |
| New component | `space_router.py` — resolves file path → space key |
| CLI extension | `main.py` — add `--spaces`, `--continue-on-error` flags |
| Engine extension | `sync.py` — pre-flight check, per-file space resolution, filtered execution |
| Client extension | `confluence_client.py` — add `check_space_access(space_key)` |

### 2. Updated Component Diagram

```
CLI  (--spaces DOCS,ENG  --continue-on-error)
 |
 v
config.resolve_active_spaces(cli_override)
 |                                 |
 v                                 v
SpaceRouter                  SyncEngine
.resolve_space(path)         .run(active_spaces, continue_on_error)
 |                                 |
 |          Pre-flight check       |
 |    ConfluenceClient.check_space_access(space_key)
 |          for each active space  |
 |                                 |
 |   Files whose mapped space      |
 |   is NOT in active_spaces       |
 |        -> SKIPPED               |
 |                                 |
 v                                 v
ConfluenceClient  (space_key resolved per-file, not from global config)
 - find_page(space_key, path)
 - create_page(space_key, ...)
 - update_page(...)
 - archive_page(...)
```

### 3. Config Model Changes (`config.py`)

**New fields on `DocSyncConfig`:**

```python
space_key: Optional[str] = None          # legacy -- single space key
space_keys: Optional[List[str]] = None   # preferred -- list of space keys
space_mappings: Dict[str, str] = {}      # folder prefix -> space key
                                         # e.g. {"docs/": "DOCS", "engineering/": "ENG"}
```

**Backward-compat validator** (runs at model construction):
```python
@model_validator(mode="after")
def coerce_space_key(self) -> "DocSyncConfig":
    if self.space_key and not self.space_keys:
        self.space_keys = [self.space_key]
    if not self.space_keys and not self.space_mappings:
        raise ValueError("At least one of space_key, space_keys, or space_mappings is required")
    return self
```

**New method:**
```python
def resolve_active_spaces(self, cli_override: Optional[List[str]] = None) -> List[str]:
    if cli_override:
        return cli_override
    if self.space_keys:
        return self.space_keys
    return [self.space_key]
```

**Sample `.docsync.yml` (new multi-space format):**
```yaml
confluence_base_url: https://myorg.atlassian.net
space_keys:
  - DOCS
  - ENG
root_page_id: "123456"
space_mappings:
  docs/: DOCS
  engineering/: ENG
  api/: DOCS
```

**Sample `.docsync.yml` (legacy format — still valid):**
```yaml
confluence_base_url: https://myorg.atlassian.net
space_key: DOCS
root_page_id: "123456"
```

### 4. New Component: SpaceRouter (`space_router.py`)

Resolves a repository file path to its target Confluence space key using longest-prefix matching.

```python
class SpaceRouter:
    def __init__(self, mappings: Dict[str, str]) -> None:
        self._mappings = sorted(mappings.items(), key=lambda kv: len(kv[0]), reverse=True)

    def resolve(self, path: str) -> Optional[str]:
        for prefix, space_key in self._mappings:
            if path.startswith(prefix):
                return space_key
        return None
```

**Routing rules:**
- Longest prefix wins: `docs/api/` beats `docs/` for `docs/api/overview.md`
- File matches no prefix → `SKIPPED` (reason: `"no space_mapping for path"`)
- Resolved space not in `active_spaces` → `SKIPPED` (reason: `"space not in --spaces filter"`)

### 5. ConfluenceClient Extension (`confluence_client.py`)

```python
@dataclass
class SpaceAccessResult:
    space_key: str
    exists: bool
    can_read: bool
    can_write: bool
    error: Optional[str] = None

def check_space_access(self, space_key: str) -> SpaceAccessResult:
    resp = self._get("/wiki/api/v2/spaces", params={"keys": space_key})
    if not resp.get("results"):
        return SpaceAccessResult(space_key=space_key, exists=False,
                                  can_read=False, can_write=False,
                                  error=f"Space {space_key!r} not found (HTTP {resp.status_code})")
    space_id = resp["results"][0]["id"]
    perms = self._get(f"/wiki/api/v2/spaces/{space_id}/permissions")
    can_write = any(p.get("operation") == "create" for p in perms.get("results", []))
    return SpaceAccessResult(space_key=space_key, exists=True,
                              can_read=True, can_write=can_write)
```

### 6. SyncEngine Extension (`sync.py`)

**Updated `_run_async` flow:**

```
1. PRE-FLIGHT: check_space_access for each active_space
   - fail AND continue_on_error=False  -> raise RuntimeError (exit immediately)
   - fail AND continue_on_error=True   -> log warning, drop space from active list
2. Build SpaceRouter(config.space_mappings)
3. list_changed_files (unchanged)
4. For each changed file:
   a. resolved_space = router.resolve(file.path)
   b. resolved_space is None OR not in active_spaces -> SyncResult(SKIPPED)
   c. Otherwise -> _process_file(file, resolved_space, contents)
5. All ConfluenceClient calls pass resolved_space (not config.space_key)
```

**`SyncResult` gains `space_key` field:**
```python
@dataclass
class SyncResult:
    path: str
    status: SyncStatus
    space_key: Optional[str] = None   # NEW
    page_id: Optional[str] = None
    error: Optional[str] = None
    fallback_used: bool = False
```

### 7. CLI Extension (`main.py`)

```python
@cli.command()
@click.option("--spaces", default=None,
              help="Comma-separated Confluence space keys (overrides config)")
@click.option("--continue-on-error", is_flag=True, default=False,
              help="Skip failing spaces instead of aborting")
def sync(config, dry_run, owner, repo, sha, spaces, continue_on_error):
    ...
    active_spaces = [s.strip() for s in spaces.split(",")] if spaces else None
    resolved = cfg.resolve_active_spaces(cli_override=active_spaces)
    engine = SyncEngine(config=cfg, github=github, confluence=confluence,
                        space_router=SpaceRouter(cfg.space_mappings))
    report = engine.run(owner, repo, sha,
                        active_spaces=resolved,
                        continue_on_error=continue_on_error)
```

### 8. Design Decisions (US-002)

| ID | Decision | Rationale |
|----|----------|-----------|
| DD-06 | Longest-prefix matching for `space_mappings` | Deterministic; matches folder-hierarchy intuition; no ambiguity |
| DD-07 | `--spaces` CLI override is total, not additive | Q2 answer; additive overrides produce hard-to-debug partial-sync states |
| DD-08 | Pre-flight auth check before any file write | Q6 answer; prevents half-synced state where some spaces succeed and others fail |
| DD-09 | `--continue-on-error` skips failed spaces, not files | Per-space semantics; per-file failures already handled by existing tenacity retry |
| DD-10 | `space_key` (singular) auto-promoted to `space_keys=[value]` | Q4 answer; no special-casing needed elsewhere in codebase |

### 9. Files Changed by US-002

| File | Change type |
|------|-------------|
| `src/docsync/config.py` | Modified — `space_keys`, `space_mappings`, `resolve_active_spaces()` |
| `src/docsync/space_router.py` | **New** — `SpaceRouter` class |
| `src/docsync/confluence_client.py` | Modified — `check_space_access()`, `SpaceAccessResult` |
| `src/docsync/sync.py` | Modified — pre-flight, per-file routing, `space_key` on `SyncResult` |
| `src/docsync/main.py` | Modified — `--spaces`, `--continue-on-error` flags |
| `tests/test_space_router.py` | **New** — unit tests for `SpaceRouter` |
| `tests/test_sync_spaces.py` | **New** — integration tests for space filtering and pre-flight |
| `tests/test_config.py` | Modified — backward compat and new fields |
