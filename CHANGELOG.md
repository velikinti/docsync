# Changelog

All notable changes to DocSync are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.0.0] — 2026-07-27

### Added

**Core Sync Engine**
- `SyncEngine` orchestrates GitHub diff → Markdown conversion → Confluence upsert/archive pipeline
- Glob-based file include/exclude filtering per `.docsync.yml`
- Async GitHub file fetching with configurable concurrency (`batch_size`)
- JSON-lines structured log output to stdout
- GitHub Actions step summary written to `$GITHUB_STEP_SUMMARY`

**GitHub Client**
- Async `httpx` client for GitHub REST API
- `list_changed_files(sha)` — classifies files as added/modified/deleted/renamed
- `fetch_files_batch(paths, ref)` — concurrent fetch with `asyncio.Semaphore`

**Markdown Converter**
- Converts GitHub Flavored Markdown to Confluence Storage Format
- Fenced code blocks → `<ac:structured-macro ac:name="code">` with language parameter
- Tables, strikethrough, task lists, footnotes, header IDs
- Inline images extracted as `ImageRef` objects for Confluence attachment upload
- XHTML validation via `lxml` with Confluence namespace declarations (`ac:`, `ri:`)
- Fallback to code-block macro if conversion produces invalid XHTML

**Confluence Client**
- Confluence REST API v2 wrapper (`httpx`)
- Page idempotency via `docsync:source_path` page property (not title)
- `find_page`, `create_page`, `update_page`, `archive_page` (trash), `upload_attachment`
- Shared `@_RETRY` tenacity decorator: 3 attempts, exponential back-off (2–30 s)
- HTTP exception sanitisation (status code + 200-char body, no auth headers)

**CLI**
- `docsync sync` command via `click`
- `--dry-run` flag: preview mode, no Confluence writes
- `--config` flag: override config file path
- Environment variable resolution: `GITHUB_TOKEN`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_USER`

**Configuration**
- `.docsync.yml` Pydantic v2 model with schema validation at startup
- Fields: `confluence_base_url`, `space_key`, `root_page_id`, `docs_root`, `include_globs`, `exclude_globs`, `batch_size`, `dry_run`

**GitHub Actions Workflow**
- Trigger on push to `main` filtering `docs/**/*.md` and `*.md`
- `workflow_dispatch` with dry-run input for manual runs
- Uploads sync log as artifact on every run

**Copilot Integration**
- `.github/instructions/docsync.instructions.md` — coding instructions for `src/docsync/**`
- `.github/prompts/requirements.prompt.md` — requirements elicitation prompt

**Tests**
- 31 unit tests across 4 modules (100% of public paths covered)
- Mock-based: no live credentials required
- pytest-asyncio + respx for async HTTP mocking

### SDLC Artifacts
- `docs/requirements.md` — 12 FR + 8 NFR with agent Q&A
- `docs/architecture.md` — component diagram, technology choices, data flow
- `docs/design-review.md` — 5 risks + 3 gaps identified and resolved
- `docs/impl-plan.md` — dependency-ordered task list (T-00 → T-82)
- `docs/code-review.md` — structured 7-area review with 5 findings
- `docs/pr-description.md` — PR description with reviewer checklist

### Known Limitations (v1)
- Folder hierarchy: all pages attach to `root_page_id` — nested parent creation deferred to v2
- `main.py` CLI has no automated test coverage
- Mermaid diagrams rendered as code blocks
- Single Confluence instance per config

---

## [1.1.0] — 2026-07-30

### Added

**Multi-Space CLI Support (US-002)**
- `--spaces` CLI flag accepts a comma-separated list of Confluence space keys (e.g. `--spaces DOCS,ENG`), completely overriding any `space_key`/`space_keys` value in `.docsync.yml` for that run
- `space_mappings` configuration block in `.docsync.yml` maps repository folder prefixes to Confluence space keys using longest-prefix matching
- `SpaceRouter` class (`src/docsync/space_router.py`) — normalises mapping keys to trailing `/`, sorts by key length descending, resolves each file path to its target space
- `--continue-on-error` flag — when set, authorization failures for individual spaces are logged as warnings; that space is skipped and sync continues for the remaining spaces
- Pre-flight authorization check via `ConfluenceClient.check_space_access()` — validates read/write permissions on all target spaces before any sync operations begin; fails fast on the first insufficient authorization (unless `--continue-on-error` is set)
- `SpaceAccessResult` dataclass — returned by `check_space_access()`; carries `space_key`, `exists`, `can_read`, `can_write`, `error`
- `SyncResult.space_key` field — each sync result now records which Confluence space the page was synced to
- `SyncReport.by_space()` method — groups sync results by space key; `""` key for results with no associated space (e.g. skipped unmapped files)
- `DocSyncConfig.space_keys` field — list form of space key configuration; preferred over single `space_key` for multi-space setups
- `DocSyncConfig.resolve_active_spaces()` — returns the effective space list for a run; precedence: CLI override > `space_keys` > `space_key` > `space_mappings` values
- Warning log and step summary "Attention" section for files with no `space_mappings` entry

**Backward Compatibility**
- Existing `.docsync.yml` files using `space_key: DOCS` (singular) continue to work without modification — `coerce_space_key` validator auto-promotes to `space_keys: [DOCS]`
- `SyncEngine` without a `space_router` argument operates in legacy single-space mode (no pre-flight, no routing)
- All 31 TC-001 baseline tests pass unchanged

**Tests (+52 new)**
- `tests/test_config.py` — 15 tests: legacy compat, multi-space fields, `resolve_active_spaces` precedence
- `tests/test_space_router.py` — 17 tests: empty router, basic routing, key normalisation, longest-prefix matching, edge cases
- `tests/test_confluence_spaces.py` — 7 tests: `check_space_access` happy/sad paths (found, not-found, 403, 404, permissions error)
- `tests/test_sync_spaces.py` — 13 tests: pre-flight abort, continue-on-error, file routing, legacy mode, `by_space()` grouping

### Architecture

- `SpaceRouter`: pure Python routing module — no HTTP, no external dependencies; 100% test coverage
- Pre-flight runs only when `space_router` is non-empty — legacy single-space configs skip it entirely
- Longest-prefix routing: keys normalised to trailing `/`; sorted by length descending; first match wins
- `check_space_access` is intentionally not wrapped in `@_RETRY` — pre-flight is a fast-fail check, not a mutating operation

### Known Limitations (v1.1)

- FR-07 (folder hierarchy) remains deferred — all pages still attach to `root_page_id`
- `_derive_parent_title` dead code retained in `sync.py` — will be activated with FR-07 in v2
- `check_space_access` has no retry — transient 403/404 during pre-flight fails the run immediately
- TOCTOU window: a permission revoked between pre-flight and the actual write will surface as a sync failure (caught by existing retry logic)

---

## [Unreleased]

### Planned for v2
- Nested parent page creation from folder structure (FR-07 complete)
- CLI integration tests via `click.testing.CliRunner`
- Native Mermaid diagram rendering macro
- `docsync rollback` subcommand
- Multi-Confluence-instance support
- Retry on `check_space_access` (configurable)
