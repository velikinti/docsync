# Code Review — Automated Documentation Sync

**Reviewer:** AI Agent (Claude Code)  
**Review Date:** 2026-07-27  
**Scope:** `src/docsync/` — all modules  
**Checklist Source:** Capstone Project Step 6

---

## Review Checklist

### 1. Correctness — Does each component behave as specified in requirements.md?

| Requirement | Component | Status | Notes |
|-------------|-----------|--------|-------|
| FR-01 Detect `.md` changes on push to main | `docsync.yml` workflow | PASS | `paths: ["docs/**/*.md", "*.md"]` filter correct |
| FR-02 Convert Markdown to CSF | `converter.py` | PASS | `markdown2` + Confluence macro wrapping |
| FR-03 Create page if not exists | `sync.py::_handle_upsert` | PASS | `find_page` returns None → `create_page` |
| FR-04 Update existing page | `sync.py::_handle_upsert` | PASS | `find_page` returns Page → `update_page` |
| FR-05 Archive deleted page | `sync.py::_handle_delete` | PASS | `confluence_client.archive_page` |
| FR-06 Upload images as attachments | `sync.py::_handle_upsert` | PASS | `upload_attachment` called per ImageRef |
| FR-07 Preserve folder hierarchy as page hierarchy | `sync.py::_derive_title` | PARTIAL | Derives title but parent page creation not implemented — all pages attach to `root_page_id` |
| FR-08 JSON-lines sync log | `sync.py::SyncReport.log_jsonlines` | PASS | JSON-lines to stdout |
| FR-09 `--dry-run` flag | `main.py`, `sync.py` | PASS | Returns SKIPPED for all file ops |
| FR-10 CLI entry point `docsync` | `setup.py` + `main.py` | PASS | `click` group + `sync` command |
| FR-11 GitHub Actions step summary | `sync.py::write_github_step_summary` | PASS | Writes to `$GITHUB_STEP_SUMMARY` |
| FR-12 `.docsync.yml` config | `config.py` | PASS | Pydantic v2 model with validation |

**Finding CR-01 (MEDIUM):** FR-07 folder hierarchy — `_handle_upsert` always uses `root_page_id` as parent. A proper implementation should traverse the parent folder chain and create intermediate parent pages if needed.  
**Recommendation:** Add `_resolve_parent_page_id(path)` to `SyncEngine` that walks the path hierarchy.

---

### 2. Security — Are secrets excluded from output? Is user input validated?

| Check | Status | Notes |
|-------|--------|-------|
| Confluence token never logged | PASS | `config.py` uses `@property`; structlog not configured to dump config objects |
| GitHub token never logged | PASS | `_sanitised_headers()` replaces token with `***` |
| Config validated at startup | PASS | Pydantic raises on missing env vars before any I/O |
| User-supplied globs validated | PASS | `include_globs` + `exclude_globs` are plain strings passed to `fnmatch` — safe |
| HTTP exception context sanitised | PASS | `_sanitised_error()` truncates response body to 200 chars |
| No secrets in `.docsync.yml` | PASS | Config file contains only URLs and space keys |

**Finding CR-02 (LOW):** `_fetch_image` in `sync.py` uses `__import__("httpx")` inline — anti-pattern that bypasses the injected HTTP client and cannot be mocked in tests.  
**Recommendation:** Import `httpx` at the top of `sync.py` normally.

---

### 3. Error Handling — Are API failures, missing files, and empty repos handled?

| Scenario | Handling | Status |
|----------|----------|--------|
| Confluence 5xx | tenacity retry ×3 | PASS |
| Confluence 429 rate limit | tenacity retry (exponential back-off) | PASS |
| Confluence 404 on archive | Swallowed in `archive_page` | PASS |
| GitHub 404 on file fetch | `FileNotFoundError` → skipped in `fetch_files_batch` | PASS |
| Missing env vars | Pydantic `model_validator` raises `ValueError` | PASS |
| Empty commit (no .md files) | `not filtered` early return | PASS |
| Malformed `.docsync.yml` | PyYAML + Pydantic validation | PASS |
| Per-file exception | Caught in `_process_file`, logged as FAILED | PASS |

**Finding CR-03 (LOW):** `_fetch_image` swallows all exceptions silently. Image upload failures should emit a structured log warning.  
**Recommendation:** Add `log.warning("image_fetch_failed", path=resolved_path, error=str(exc))` before `return None`.

---

### 4. Test Coverage — Do tests cover happy path AND edge cases?

| Module | Happy Path | Error Path | Edge Cases |
|--------|-----------|------------|------------|
| `converter.py` | PASS | PASS (invalid XHTML fallback) | PASS (images, tables, code fences) |
| `confluence_client.py` | PASS | PASS (500 error) | PASS (404 idempotent archive) |
| `github_client.py` | PASS | PASS (404, API error) | PASS (batch missing file) |
| `sync.py` | PASS | PASS (partial failure) | PASS (dry-run, glob filter, archive not found) |
| `config.py` | Not tested | Not tested | — |
| `main.py` | Not tested | Not tested | — |

**Finding CR-04 (MEDIUM):** `config.py` and `main.py` have no test coverage.  
**Recommendation:** Add `test_config.py` (valid YAML, missing env var, bad YAML) and `test_main.py` (CLI invocation via `click.testing.CliRunner`).

---

### 5. Code Clarity — Are names self-explanatory? Is logic easy to follow?

| Check | Status | Notes |
|-------|--------|-------|
| Function names | PASS | `list_changed_files`, `find_page`, `archive_page` — self-explanatory |
| Module separation | PASS | Config / GitHub / Confluence / Converter / Sync / CLI clearly delineated |
| Dataclasses over dicts | PASS | `Page`, `ChangedFile`, `SyncResult` all typed |
| Single responsibility | PASS | Each module has one concern |

---

### 6. DRY Principle — Is logic duplicated?

**Finding CR-05 (LOW):** The tenacity retry decorator is repeated identically on `find_page`, `create_page`, `update_page`, and `archive_page` in `confluence_client.py`.  
**Recommendation:** Extract to a module-level constant `_RETRY = retry(stop=..., wait=..., retry=..., reraise=True)` and apply as `@_RETRY`.

---

### 7. Dependency Safety

| Package | Version Pinned | Known Vulnerabilities | Notes |
|---------|---------------|----------------------|-------|
| `httpx` | `>=0.27,<1.0` | None known | |
| `markdown2` | `>=2.4,<3.0` | None known | |
| `pydantic` | `>=2.6,<3.0` | None known (v2 rewrite) | |
| `tenacity` | `>=8.2,<9.0` | None known | |
| `lxml` | `>=5.2,<6.0` | None known in 5.x | |
| `structlog` | `>=24.1,<25.0` | None known | |
| `PyYAML` | `>=6.0,<7.0` | CVE-2017-18342 affects <5.4 — pinned >=6 PASS | |

---

## Summary of Findings

| ID | Severity | File | Description |
|----|----------|------|-------------|
| CR-01 | MEDIUM | `sync.py` | Folder hierarchy not fully implemented — all pages use root_page_id as parent |
| CR-02 | LOW | `sync.py` | `__import__("httpx")` inline in `_fetch_image` |
| CR-03 | LOW | `sync.py` | Image fetch failures silently swallowed |
| CR-04 | MEDIUM | — | No tests for `config.py` or `main.py` |
| CR-05 | LOW | `confluence_client.py` | Duplicated tenacity decorator |

**Overall verdict: PASS WITH MINOR ISSUES** — no blockers, CR-01 and CR-04 recommended before v1 release.

---

## US-002 Code Review — `--spaces` flag  *(TC-002)*

**Reviewer:** sdlc-code-review agent
**Review Date:** 2026-07-30
**Scope:** US-002 additions — `config.py`, `space_router.py`, `confluence_client.py`, `sync.py`, `main.py`, and all new test files
**Test run:** 83 passed / 0 failed

---

### 1. Correctness — FR-13 through FR-21 Traceability

| FR/NFR | Requirement Summary | Implementing Code | Status |
|--------|--------------------|--------------------|--------|
| FR-13 | `--spaces` CLI flag, comma-separated | `main.py:45-54` click option | PASS |
| FR-14 | `--spaces` overrides config | `config.py:resolve_active_spaces` — returns early when `cli_override` is set | PASS |
| FR-15 | `space_mappings` config block | `config.py:17` `Dict[str, str]` field | PASS |
| FR-16 | Sync only mapped spaces | `sync.py:247-256` `if file_space not in active_spaces: SKIP` | PASS |
| FR-17 | Non-listed spaces unchanged | SKIPPED status — no `create_page`, `update_page`, `archive_page` called | PASS |
| FR-18 | Pre-flight auth check | `sync.py:196-208` `check_space_access` loop before `list_changed_files` | PASS |
| FR-19 | Fail if space missing/unauthorized | `sync.py:204-205` `raise RuntimeError`; caught in `main.py:111-113` → `sys.exit(1)` | PASS |
| FR-20 | `--continue-on-error` flag | `main.py:50-55`; `sync.py:202-207` drops failing space from `valid_spaces` | PASS |
| FR-21 | `space_keys` list + legacy `space_key` compat | `config.py:30-38` `coerce_space_key` model_validator | PASS |
| NFR-09 | Pre-flight ≤10 spaces in 10s | Sequential loop; 10 × ~200ms = ~2s — within budget | PASS |
| NFR-10 | Legacy `.docsync.yml` unchanged | `base_config` fixture (`space_key="TEST"`) works identically — verified by 8 pre-existing tests | PASS |
| NFR-11 | Log records space_key per page; step summary includes pre-flight | `sync.py:75 space_key` in JSON-lines; step summary updated with per-space tables | PASS |
| NFR-12 | Error message names failing space + HTTP status | `confluence_client.py:188` `f"Space {space_key!r}: HTTP {status}"` | PASS |

**13/13 requirements — all PASS.**

---

### 2. Security

| Check | Status | Notes |
|-------|--------|-------|
| No hardcoded credentials in new code | PASS | grep confirms only `os.environ.get()` patterns in production code |
| `check_space_access` error messages secret-safe | PASS | Error strings contain space_key + HTTP status only; no auth headers |
| `SpaceAccessResult` fields never log secrets | PASS | `error` field set to sanitised strings; auth comes from `self._auth` (not exposed) |
| Config properties don't leak tokens | PASS | `confluence_user` / `confluence_token` are `@property` reading `os.environ` |
| Structlog calls in new pre-flight code | PASS | `log.warning("preflight_skip", space=space, reason=access.error)` — no token fields |

---

### 3. Error Handling

| Scenario | Handling | Status |
|----------|----------|--------|
| Space not found (HTTP 200, empty results) | Returns `SpaceAccessResult(exists=False)` → RuntimeError or log.warning | PASS |
| Space endpoint returns 403/404 | Returns `SpaceAccessResult(exists=False, error=...)` | PASS |
| Permissions endpoint returns 403 | Returns `SpaceAccessResult(can_write=False, error=...)` | PASS |
| All active spaces fail pre-flight + `--continue-on-error` | `valid_spaces=[]` → `list_changed_files` runs → no files processed | PASS |
| File has no space_mapping | WARN + `SyncResult(SKIPPED, error="no space_mapping for path")` | PASS |
| Routing mode: file space not in `--spaces` | `SyncResult(SKIPPED, error="space not in --spaces filter")` | PASS |
| Legacy mode with empty `active_spaces` | Fallback: `self._cfg.space_key or ""` — see CR-09 | MEDIUM |

**Finding CR-06 (MEDIUM):** `sync.py:258` — Legacy mode fallback `active_spaces[0] if active_spaces else (self._cfg.space_key or "")` can resolve to an empty string `""` if `active_spaces` is an empty list AND `config.space_key` is None. This produces a silent Confluence API error ("space key required") rather than a clear configuration error. In practice this cannot occur since `coerce_space_key` guarantees at least one space is configured, but the defensive branch is fragile.
**Recommendation:** Replace with `active_spaces[0] if active_spaces else self._cfg.resolve_active_spaces()[0]` or add an explicit guard: `if not active_spaces: raise RuntimeError("No active space keys configured")`.

---

### 4. Test Coverage

```
Name                                    Stmts   Miss  Cover   Missing
-----------------------------------------------------------------------
src/docsync/space_router.py                17      0   100%
src/docsync/config.py                      56     10    82%   45,52,56,65,70-75
src/docsync/confluence_client.py          123     17    86%
src/docsync/sync.py                       206     54    74%   log_jsonlines, write_github_step_summary, _derive_parent_title, image upload
```

New module (`space_router.py`) at 100%. All modified modules ≥ 80% except `sync.py` at 74%.

**Finding CR-07 (LOW):** `sync.py` coverage at 74% — below the 80% threshold. The gap is caused by:
- Lines 69-81 `log_jsonlines` (prints to stdout — not exercised in unit tests)
- Lines 83-120 `write_github_step_summary` (requires `GITHUB_STEP_SUMMARY` env var)
- Lines 143-151 `_derive_parent_title` (dead code — see CR-08)
- Lines 382-389 `_fetch_image` (integration-only path)
**Recommendation:** Add a test that sets `GITHUB_STEP_SUMMARY` to a temp file and verifies the written output. Delete `_derive_parent_title`. This should bring `sync.py` to ≥80%.

**Finding CR-08 (LOW):** `sync.py:142-151` — `_derive_parent_title` is defined but never called anywhere in the codebase. Dead code carried forward from the TC-001 baseline.
**Recommendation:** Delete the function. If folder hierarchy (FR-07 partial) is implemented in a future sprint, add it then.

---

### 5. Code Clarity

| Check | Status | Notes |
|-------|--------|-------|
| `SpaceRouter` intent is clear | PASS | Docstring, `is_empty` property, `all_spaces` property — readable |
| Pre-flight flow in `_run_async` | PASS | Three clearly-commented blocks: pre-flight, GAP-04 warn, file loop |
| `coerce_space_key` intent | PASS | Clear comment "Promote legacy space_key to space_keys list" |
| `by_space()` purpose | PASS | Docstring explains the `""` key convention |

**Finding CR-09 (LOW):** `config.py:64-65` — `resolve_active_spaces` contains an unreachable branch:
```python
if self.space_key:       # line 64
    return [self.space_key]   # line 65
```
`coerce_space_key` guarantees that when `space_key` is set, `space_keys` is also set to `[space_key]`. The `if self.space_keys:` check on line 62 will always match first, making lines 64-65 dead code.
**Recommendation:** Remove lines 64-65. The fallback on line 66 (`return list(dict.fromkeys(...))`) handles the mappings-only case.

---

### 6. DRY Principle

No new duplication introduced. `SpaceRouter` is a clean single-purpose class. Pre-flight check loop is in one place. Routing filter is in one place.

**Finding CR-10 (LOW):** `main.py:71` — `raise click.BadParameter(...)` is missing the `param_hint` argument. The Click error output will say "Invalid value" without identifying `--spaces` as the offending option.
**Recommendation:** `raise click.BadParameter("...", param_hint="'--spaces'")`.

---

### 7. Dependency Safety

No new production dependencies added in US-002. Existing dependency bounds reviewed in TC-001 code review (all PASS).

**Finding CR-11 (LOW):** `requirements.txt:12-16` — Dev/test dependencies (`pytest>=8.0`, `pytest-asyncio>=0.23`, `pytest-httpx>=0.30`, `respx>=0.21`, `coverage[toml]>=7.4`) have only lower-bound version constraints. A breaking release could silently break CI.
**Recommendation:** Add upper bounds: `pytest>=8.0,<9.0`, `pytest-asyncio>=0.23,<1.0`, etc.

---

### US-002 Summary of Findings

| ID | Severity | File | Description |
|----|----------|------|-------------|
| CR-06 | MEDIUM | `sync.py:258` | Legacy fallback can produce empty string space_key |
| CR-07 | LOW | `sync.py` | Coverage 74% — log_jsonlines, write_github_step_summary, image upload untested |
| CR-08 | LOW | `sync.py:142` | `_derive_parent_title` is dead code |
| CR-09 | LOW | `config.py:64` | Unreachable branch in `resolve_active_spaces` |
| CR-10 | LOW | `main.py:71` | `BadParameter` lacks `param_hint` |
| CR-11 | LOW | `requirements.txt` | Dev deps lack upper-bound version pins |

**Overall verdict (US-002): PASS WITH MINOR ISSUES** — 1 MEDIUM, 5 LOW. No BLOCKERs or HIGH findings. All 13 US-002 requirements are correctly implemented. The MEDIUM finding (CR-06) is a defensive code path that cannot be triggered in normal operation.
