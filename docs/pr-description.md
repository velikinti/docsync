# Pull Request: Automated Documentation Sync — Full SDLC Implementation

**PR Title:** feat: implement Automated Documentation Sync (DocSync) with full SDLC pipeline

---

## Summary

Implements **DocSync**, a Python CLI tool and GitHub Actions workflow that automatically syncs Markdown documentation from GitHub repositories to Confluence Cloud on every merge to `main`. The entire implementation was driven through an Agentic SDLC pipeline — from requirements elicitation through architecture, design review, implementation planning, coding, code review, and verification — completing all eight capstone phases.

---

## Changes Made

### SDLC Artifacts
| File | Reason |
|------|--------|
| `docs/requirements.md` | FR/NFR requirements with agent Q&A clarifications |
| `docs/architecture.md` | Component diagram, technology choices, data flow |
| `docs/design-review.md` | Risk/gap analysis with 5 risks identified and resolved |
| `docs/impl-plan.md` | Dependency-ordered task list (T-00 → T-82) |
| `docs/code-review.md` | Structured review covering all 6 checklist areas |

### Source Code
| File | Reason |
|------|--------|
| `src/docsync/config.py` | Pydantic v2 config model for `.docsync.yml`; validates env vars at startup |
| `src/docsync/github_client.py` | Async httpx GitHub REST client; batch file fetch with semaphore |
| `src/docsync/converter.py` | Markdown → Confluence Storage Format; fenced code → `ac:structured-macro`; lxml XHTML validation |
| `src/docsync/confluence_client.py` | Confluence REST client; property-based idempotency (`docsync:source_path`); shared `@_RETRY` decorator |
| `src/docsync/sync.py` | SyncEngine: diff → filter → upsert/archive pipeline; JSON-lines log; GH step summary |
| `src/docsync/main.py` | `click` CLI entry point with `--dry-run` and `--config` |
| `src/docsync/__init__.py` | Public API surface |
| `setup.py` | Pip-installable package with `docsync` console script |
| `requirements.txt` | Pinned runtime + dev dependencies |

### Infrastructure & Config
| File | Reason |
|------|--------|
| `.github/workflows/docsync.yml` | GitHub Actions workflow triggered on push to `main` |
| `.github/instructions/docsync.instructions.md` | Copilot coding instructions for `src/docsync/**` |
| `.github/prompts/requirements.prompt.md` | Copilot requirements elicitation prompt file |
| `.docsync.yml` | Example configuration at repo root |
| `README.md` | Full documentation: installation, config reference, local dev guide |

### Tests
| File | Reason |
|------|--------|
| `tests/conftest.py` | Shared fixtures: mock Confluence, mock GitHub, env vars |
| `tests/test_confluence_client.py` | 7 tests: find/create/update/archive, idempotency, error handling |
| `tests/test_converter.py` | 10 tests: GFM constructs, code macros, images, fallback |
| `tests/test_github_client.py` | 6 tests: changed files, content fetch, batch, 404 handling |
| `tests/test_sync.py` | 8 tests: happy path, dry-run, deletion, glob filtering, partial failure |

---

## Test Evidence

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.0.2
asyncio: mode=Mode.STRICT

collected 31 items

tests/test_confluence_client.py .......                [ 22%]
tests/test_converter.py ..........                     [ 54%]
tests/test_github_client.py ......                     [ 74%]
tests/test_sync.py ........                            [100%]

============================= 31 passed in 8.96s ==============================

Coverage Summary:
  src/docsync/__init__.py          100%
  src/docsync/config.py             77%
  src/docsync/confluence_client.py  82%
  src/docsync/converter.py          96%
  src/docsync/github_client.py      92%
  src/docsync/sync.py               74%
  src/docsync/main.py                0%   (CLI, covered via integration)
  TOTAL                             76%
```

---

## Known Limitations

| Limitation | Notes |
|------------|-------|
| FR-07 Folder hierarchy partially implemented | All pages attach to `root_page_id`; nested parent page creation deferred to v2 |
| `main.py` test coverage is 0% | CLI covered by manual dry-run testing; `CliRunner` tests deferred to v2 |
| Mermaid diagrams | Rendered as code blocks; native Mermaid macro support deferred to v2 |
| Single Confluence instance | Multi-instance support out of scope |
| Sync rollback | Partially synced state requires re-run (idempotent); rollback subcommand deferred to v2 |

---

## Reviewer Checklist

Before approving this PR, please confirm:

- [ ] **Requirements coverage** — Every FR-01 through FR-12 has corresponding implementation code
- [ ] **NFR-01 Security** — No secrets in code, config files, or logs; verify `.docsync.yml` contains no credentials
- [ ] **NFR-03 Reliability** — Tenacity retry decorator present on all mutating Confluence calls
- [ ] **NFR-07 Idempotency** — `find_page` uses `docsync:source_path` property, not page title
- [ ] **Test pass** — `pytest tests/ -v` reports 31 passed, 0 failed
- [ ] **Dry-run works** — `docsync sync --dry-run` exits 0 with no Confluence writes
- [ ] **Architecture matches code** — Component names in `docs/architecture.md` match module names in `src/docsync/`
- [ ] **Design review fixes applied** — DD-01 (property lookup), DD-02 (async fetch), DD-03 (fallback conversion), DD-04 (trash archive), DD-05 (sanitised exceptions) all present
- [ ] **No secrets in git history** — Run `git log --all --full-history -- "**/.env"` confirms clean
- [ ] **README is accurate** — Local dev guide and config reference match current implementation

---

---

# Pull Request: Multi-Space Support (`--spaces` flag) — TC-002 / US-002

**PR Title:** feat(US-002): add `--spaces` flag and multi-space routing to DocSync CLI

---

## Summary

Adds multi-Confluence-space support to DocSync by implementing a `--spaces` CLI flag, a `space_mappings` config block, and a `SpaceRouter` class that routes repository file paths to Confluence space keys using longest-prefix matching. The feature includes pre-flight authorization checks on all target spaces, a `--continue-on-error` flag for graceful space-level failure handling, and full backward compatibility with existing single-`space_key` configurations. The entire feature was developed through an 8-phase Agentic SDLC pipeline — requirements → architecture → design review → implementation planning → implementation → code review → verification → PR — with human approval required at every phase transition.

---

## Changes Made

### SDLC Artifacts
| File | Reason |
|------|--------|
| `docs/requirements.md` | Appended US-002 section: FR-13..FR-21, NFR-09..NFR-12, clarification Q&A |
| `docs/architecture.md` | Appended US-002 section: SpaceRouter, multi-space engine flow, config schema |
| `docs/design-review.md` | US-002 design review: 4 risks, 2 gaps, 8 design decisions, 5 required architecture updates |
| `docs/impl-plan.md` | Appended US-002 task plan: Groups A–F (T-10 to T-55), acceptance criteria |
| `docs/code-review.md` | Appended US-002 code review: 6 findings CR-06..CR-11, 13/13 requirements PASS, verdict PASS |
| `docs/verification.md` | Appended TC-002 verification: 83 tests, 75% coverage, FR traceability matrix, PASS verdict |
| `docs/pr-description.md` | This file — PR description for TC-002 / US-002 |

### Source Code
| File | Change | Reason |
|------|--------|--------|
| `src/docsync/space_router.py` | **NEW** | `SpaceRouter` class — longest-prefix routing from repo paths to Confluence space keys; key normalisation; `is_empty`, `all_spaces`, `resolve()` |
| `src/docsync/config.py` | **MODIFIED** | `space_key` → Optional; added `space_keys: List[str]`, `space_mappings: Dict[str, str]`; `coerce_space_key` validator for legacy compat; `resolve_active_spaces()` method |
| `src/docsync/confluence_client.py` | **MODIFIED** | Added `SpaceAccessResult` dataclass; added `check_space_access(space_key)` method for pre-flight authorization checks |
| `src/docsync/sync.py` | **MODIFIED** | `SyncResult.space_key` field; `SyncReport.by_space()` grouping method; `SyncEngine` accepts `space_router` parameter; pre-flight loop; per-file routing with skip/warn logic; `--continue-on-error` handling |
| `src/docsync/main.py` | **MODIFIED** | Added `--spaces` click option (comma-separated, validated); `--continue-on-error` flag; `SpaceRouter` wiring; `resolve_active_spaces` call; pre-flight `RuntimeError` catch |
| `src/docsync/__init__.py` | **MODIFIED** | Exported `SpaceAccessResult`, `SpaceRouter` in public API |

### Infrastructure & Config
| File | Change | Reason |
|------|--------|--------|
| `.docsync.yml.example` | **NEW** | Updated example showing multi-space config (`space_keys`, `space_mappings`) and legacy single-`space_key` config |
| `.github/instructions/phase-1-requirements.instructions.md` | existing | US-002 requirements phase |
| `.github/instructions/phase-2-architecture.instructions.md` | existing | US-002 architecture phase |
| `.github/instructions/phase-3-design-review.instructions.md` | existing | US-002 design review phase |
| `.github/instructions/phase-4-impl-planning.instructions.md` | existing | US-002 implementation planning phase |
| `.github/instructions/phase-6-code-review.instructions.md` | existing | US-002 code review phase |
| `.github/instructions/phase-7-verification.instructions.md` | existing | US-002 verification phase |
| `.github/instructions/phase-8-pr.instructions.md` | existing | US-002 PR creation phase |

### Tests
| File | Change | What It Covers |
|------|--------|----------------|
| `tests/test_config.py` | **NEW** | 15 tests — `TestLegacyBackwardCompat` (legacy `space_key` promotion), `TestMultiSpaceFields` (`space_keys`, `space_mappings`, validation errors), `TestResolveActiveSpaces` (CLI override precedence, fallback ordering) |
| `tests/test_space_router.py` | **NEW** | 17 tests — `TestEmptyRouter`, `TestBasicRouting`, `TestKeyNormalisation` (trailing `/` normalisation), `TestLongestPrefixMatching` (3-level depth), `TestEdgeCases` |
| `tests/test_confluence_spaces.py` | **NEW** | 7 tests — `check_space_access()`: space found+writable, found+read-only, found+no-permissions-entries, not-found (empty results), 403, 404, permissions-endpoint 403 |
| `tests/test_sync_spaces.py` | **NEW** | 13 tests — `TestPreflightAbort` (fail fast, no files processed), `TestPreflightContinueOnError` (failing space dropped, others continue), `TestFileRouting` (mapped/active, mapped/inactive, unmapped, mixed), `TestLegacySingleSpaceMode` (no router, legacy `find_page`), `TestSyncReportBySpace` (`by_space()` grouping) |
| `tests/conftest.py` | unchanged | `base_config` fixture with `space_key="TEST"` continues to work via `coerce_space_key` auto-promotion |

---

## Test Evidence

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.0.2, pluggy-1.6.0 -- python.exe
rootdir: C:\Projects\Capstone_Project\GitHub-Copilot-Capstone-Project
asyncio: mode=Mode.STRICT
collecting ... collected 83 items

tests/test_config.py::TestLegacyBackwardCompat::test_space_key_promoted_to_space_keys PASSED [  1%]
tests/test_config.py::TestLegacyBackwardCompat::test_space_key_preserved_alongside_space_keys PASSED [  2%]
tests/test_config.py::TestLegacyBackwardCompat::test_existing_base_config_valid PASSED [  3%]
tests/test_config.py::TestLegacyBackwardCompat::test_strip_trailing_slash_on_url PASSED [  4%]
tests/test_config.py::TestMultiSpaceFields::test_space_keys_list_accepted PASSED [  6%]
tests/test_config.py::TestMultiSpaceFields::test_space_mappings_accepted PASSED [  7%]
tests/test_config.py::TestMultiSpaceFields::test_space_keys_not_promoted_when_already_set PASSED [  8%]
tests/test_config.py::TestMultiSpaceFields::test_missing_all_space_fields_raises PASSED [  9%]
tests/test_config.py::TestMultiSpaceFields::test_space_mappings_alone_is_sufficient PASSED [ 10%]
tests/test_config.py::TestResolveActiveSpaces::test_cli_override_takes_precedence PASSED [ 12%]
tests/test_config.py::TestResolveActiveSpaces::test_space_keys_returned_when_no_override PASSED [ 13%]
tests/test_config.py::TestResolveActiveSpaces::test_legacy_space_key_returned_when_no_space_keys PASSED [ 14%]
tests/test_config.py::TestResolveActiveSpaces::test_mappings_values_returned_as_fallback PASSED [ 15%]
tests/test_config.py::TestResolveActiveSpaces::test_cli_override_as_empty_list_returns_empty PASSED [ 16%]
tests/test_config.py::TestResolveActiveSpaces::test_cli_override_multi_space PASSED [ 18%]
tests/test_confluence_client.py::TestFindPage::test_finds_page_by_source_path PASSED [ 19%]
tests/test_confluence_client.py::TestFindPage::test_returns_none_when_not_found PASSED [ 20%]
tests/test_confluence_client.py::TestFindPage::test_raises_on_api_error PASSED [ 21%]
tests/test_confluence_client.py::TestCreatePage::test_creates_page_successfully PASSED [ 22%]
tests/test_confluence_client.py::TestUpdatePage::test_updates_page_successfully PASSED [ 24%]
tests/test_confluence_client.py::TestArchivePage::test_archives_page PASSED [ 25%]
tests/test_confluence_client.py::TestArchivePage::test_archive_idempotent_on_404 PASSED [ 26%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessFound::test_space_found_and_writable PASSED [ 27%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessFound::test_space_found_but_read_only PASSED [ 28%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessFound::test_space_found_but_no_permissions_entries PASSED [ 30%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessNotFound::test_space_not_found_empty_results PASSED [ 31%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessNotFound::test_spaces_endpoint_returns_403 PASSED [ 32%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessNotFound::test_spaces_endpoint_returns_404 PASSED [ 33%]
tests/test_confluence_spaces.py::TestCheckSpaceAccessPermissionsError::test_permissions_endpoint_returns_403 PASSED [ 34%]
tests/test_converter.py::TestConvert::test_basic_markdown_converts PASSED [ 36%]
tests/test_converter.py::TestConvert::test_code_fence_becomes_confluence_macro PASSED [ 37%]
tests/test_converter.py::TestConvert::test_table_converts PASSED         [ 38%]
tests/test_converter.py::TestConvert::test_relative_image_extracted PASSED [ 39%]
tests/test_converter.py::TestConvert::test_absolute_image_not_extracted PASSED [ 40%]
tests/test_converter.py::TestConvert::test_invalid_xhtml_triggers_fallback PASSED [ 42%]
tests/test_converter.py::TestConvert::test_empty_markdown PASSED         [ 43%]
tests/test_converter.py::TestConvert::test_bold_italic PASSED            [ 44%]
tests/test_converter.py::TestApplyAttachmentUrls::test_rewrites_src_after_upload PASSED [ 45%]
tests/test_converter.py::TestApplyAttachmentUrls::test_no_images_returns_unchanged_body PASSED [ 46%]
tests/test_github_client.py::TestListChangedFiles::test_lists_added_and_modified_files PASSED [ 48%]
tests/test_github_client.py::TestListChangedFiles::test_raises_on_api_error PASSED [ 49%]
tests/test_github_client.py::TestGetFileContent::test_decodes_base64_content PASSED [ 50%]
tests/test_github_client.py::TestGetFileContent::test_raises_file_not_found PASSED [ 51%]
tests/test_github_client.py::TestFetchFilesBatch::test_fetches_multiple_files PASSED [ 53%]
tests/test_github_client.py::TestFetchFilesBatch::test_skips_missing_files PASSED [ 54%]
tests/test_space_router.py::TestEmptyRouter::test_is_empty_true PASSED   [ 55%]
tests/test_space_router.py::TestEmptyRouter::test_resolve_returns_none PASSED [ 56%]
tests/test_space_router.py::TestEmptyRouter::test_all_spaces_empty PASSED [ 57%]
tests/test_space_router.py::TestBasicRouting::test_resolve_exact_prefix PASSED [ 59%]
tests/test_space_router.py::TestBasicRouting::test_resolve_nested_path PASSED [ 60%]
tests/test_space_router.py::TestBasicRouting::test_resolve_no_match_returns_none PASSED [ 61%]
tests/test_space_router.py::TestBasicRouting::test_all_spaces_unique_ordered PASSED [ 62%]
tests/test_space_router.py::TestKeyNormalisation::test_key_without_trailing_slash_normalised PASSED [ 63%]
tests/test_space_router.py::TestKeyNormalisation::test_key_with_trailing_slash_unchanged PASSED [ 65%]
tests/test_space_router.py::TestKeyNormalisation::test_both_forms_equivalent PASSED [ 66%]
tests/test_space_router.py::TestLongestPrefixMatching::test_longer_prefix_wins PASSED [ 67%]
tests/test_space_router.py::TestLongestPrefixMatching::test_shorter_prefix_matches_non_api_path PASSED [ 68%]
tests/test_space_router.py::TestLongestPrefixMatching::test_three_levels_longest_wins PASSED [ 69%]
tests/test_space_router.py::TestLongestPrefixMatching::test_identical_length_prefixes_different_spaces PASSED [ 71%]
tests/test_space_router.py::TestEdgeCases::test_path_with_no_slash_does_not_match_prefix PASSED [ 72%]
tests/test_space_router.py::TestEdgeCases::test_is_empty_false_when_has_mappings PASSED [ 73%]
tests/test_space_router.py::TestEdgeCases::test_multiple_spaces_all_spaces_deduped PASSED [ 74%]
tests/test_sync.py::TestSyncEngineHappyPath::test_creates_new_page_for_added_file PASSED [ 75%]
tests/test_sync.py::TestSyncEngineHappyPath::test_updates_existing_page PASSED [ 77%]
tests/test_sync.py::TestSyncEngineHappyPath::test_archives_deleted_file PASSED [ 78%]
tests/test_sync.py::TestSyncEngineHappyPath::test_skips_deleted_file_not_in_confluence PASSED [ 79%]
tests/test_sync.py::TestDryRun::test_dry_run_skips_all_writes PASSED     [ 80%]
tests/test_sync.py::TestGlobFiltering::test_excluded_files_are_skipped PASSED [ 81%]
tests/test_sync.py::TestPartialFailure::test_failure_on_one_file_does_not_stop_others PASSED [ 83%]
tests/test_sync.py::TestSyncReport::test_counts_are_correct PASSED       [ 84%]
tests/test_sync_spaces.py::TestPreflightAbort::test_raises_when_space_not_found PASSED [ 85%]
tests/test_sync_spaces.py::TestPreflightAbort::test_no_files_processed_on_preflight_failure PASSED [ 86%]
tests/test_sync_spaces.py::TestPreflightContinueOnError::test_failing_space_dropped_others_continue PASSED [ 87%]
tests/test_sync_spaces.py::TestPreflightContinueOnError::test_all_spaces_fail_returns_empty_report PASSED [ 89%]
tests/test_sync_spaces.py::TestFileRouting::test_file_mapped_to_active_space_is_synced PASSED [ 90%]
tests/test_sync_spaces.py::TestFileRouting::test_file_mapped_to_inactive_space_is_skipped PASSED [ 91%]
tests/test_sync_spaces.py::TestFileRouting::test_unmapped_file_is_skipped_with_warning PASSED [ 92%]
tests/test_sync_spaces.py::TestFileRouting::test_mixed_files_routed_correctly PASSED [ 93%]
tests/test_sync_spaces.py::TestLegacySingleSpaceMode::test_legacy_engine_works_without_router PASSED [ 95%]
tests/test_sync_spaces.py::TestLegacySingleSpaceMode::test_legacy_find_page_uses_space_key PASSED [ 96%]
tests/test_sync_spaces.py::TestSyncReportBySpace::test_by_space_groups_correctly PASSED [ 97%]
tests/test_sync_spaces.py::TestSyncReportBySpace::test_by_space_empty_report PASSED [ 98%]
tests/test_sync_spaces.py::TestSyncReportBySpace::test_by_space_all_same_space PASSED [100%]

============================= 83 passed in 8.47s ==============================
```

Coverage table:
```
Name                               Stmts   Miss  Cover   Missing
----------------------------------------------------------------
src\docsync\__init__.py                7      0   100%
src\docsync\config.py                 56     10    82%   45, 52, 56, 65, 70-75
src\docsync\confluence_client.py     123     17    86%   120-121, 150-151, 172, 231-249
src\docsync\converter.py              75      3    96%   125-127
src\docsync\github_client.py          73      6    92%   44-47, 91, 98
src\docsync\main.py                   67     67     0%   3-132
src\docsync\space_router.py           17      0   100%
src\docsync\sync.py                  206     54    74%   70-71, 84-120, 125, 143-151, 214, 285, 315-323, 326, 382-389
----------------------------------------------------------------
TOTAL                                624    157    75%
============================= 83 passed in 8.77s ==============================
```

---

## Known Limitations

| ID | Limitation | Why Deferred |
|----|-----------|-------------|
| CR-06 MEDIUM | `file_space` in legacy routing can evaluate to `""` if both `active_spaces` and `space_key` are unset | Unreachable in practice — `coerce_space_key` validator prevents this config from being created. Will be cleaned up with FR-07 parent-hierarchy work in v2. |
| CR-08 LOW | `_derive_parent_title` dead code retained in `sync.py` | Will be reactivated when FR-07 nested parent page creation is implemented in v2. Removing it now would delete needed future code. |
| CR-09 LOW | `check_space_access` has no `@_RETRY` tenacity decorator | Pre-flight is a fast-fail check, not a mutating operation. Retrying a 403 or 404 during pre-flight would mislead the operator. Intentional design (DD-08). |
| CR-10 LOW | Unreachable branch in `resolve_active_spaces` (`if self.space_key: return [self.space_key]`) | Consequence of `coerce_space_key` always promoting `space_key` → `space_keys`. Will be cleaned up in v2 config refactor. |
| GAP-04 resolved | `--spaces XYZ` when XYZ has no `space_mappings` entry emits WARNING, not error | Teams may legitimately pass a space key before adding mappings. Warning is surfaced in step summary "Attention" section per DD-13. |
| RISK-07 LOW | TOCTOU window: permission could be revoked between pre-flight and sync write | Transient 403s during writes are caught by `tenacity` retry. Documented as known limitation per design review. |

---

## Reviewer Checklist

### US-002 New Functionality

- [ ] **FR-13 `--spaces` flag** — `src/docsync/main.py:45-55` — verify `click.option("--spaces")` with comma-split validation
- [ ] **FR-14 CLI override** — `src/docsync/config.py:58-66` — `resolve_active_spaces(cli_override)` returns `list(cli_override)` immediately when set
- [ ] **FR-15 `space_mappings` config** — `src/docsync/config.py:17` — `space_mappings: Dict[str, str]` field; `src/docsync/space_router.py` — `SpaceRouter` consumes it
- [ ] **FR-16 File routing** — `src/docsync/sync.py` — per-file `router.resolve(path)` call; skipped with `"space not in --spaces filter"` if resolved space not in `active_spaces`
- [ ] **FR-17 Non-listed spaces untouched** — `tests/test_sync_spaces.py::TestFileRouting::test_file_mapped_to_inactive_space_is_skipped` — verify `create_page`/`update_page`/`archive_page` not called for inactive spaces
- [ ] **FR-18 Pre-flight auth check** — `src/docsync/sync.py` — `check_space_access(space_key)` loop before `list_changed_files` call; only when `not router.is_empty`
- [ ] **FR-19 Fail-fast on bad space** — `tests/test_sync_spaces.py::TestPreflightAbort::test_raises_when_space_not_found` — `RuntimeError("Pre-flight failed...")` raised; `mock_gh.list_changed_files.assert_not_called()`
- [ ] **FR-20 `--continue-on-error`** — `src/docsync/main.py:50-55` — click flag wired to `engine.run(continue_on_error=...)`; `tests/test_sync_spaces.py::TestPreflightContinueOnError::test_failing_space_dropped_others_continue`
- [ ] **FR-21 Legacy compat** — `tests/test_config.py::TestLegacyBackwardCompat::test_space_key_promoted_to_space_keys` — `space_key="DOCS"` → `space_keys=["DOCS"]`; `tests/test_sync_spaces.py::TestLegacySingleSpaceMode::test_legacy_engine_works_without_router`

### Design Decisions (US-002)

- [ ] **DD-06 Longest-prefix matching** — `src/docsync/space_router.py` — `_mappings` sorted by `len(key)` descending; `test_space_router.py::TestLongestPrefixMatching::test_longer_prefix_wins`
- [ ] **DD-07 `--spaces` total override** — `config.py::resolve_active_spaces` returns early on `cli_override`; no merging with config values
- [ ] **DD-08 Pre-flight before writes** — verify `check_space_access` loop precedes `list_changed_files` in `sync.py::_run_async`
- [ ] **DD-09 `--continue-on-error` drops spaces** — `valid_spaces` list built from pre-flight; failing spaces excluded; remaining processed
- [ ] **DD-10 Auto-promote legacy `space_key`** — `config.py::coerce_space_key` validator; existing `.docsync.yml` files require zero changes
- [ ] **DD-11 Unmapped files emit WARNING** — `log.warning("no_space_mapping")` present; step summary "Attention" section lists unmapped paths
- [ ] **DD-12 Keys normalised to trailing `/`** — `SpaceRouter.__init__` applies `k if k.endswith("/") else k + "/"` to all mapping keys
- [ ] **DD-13 Unknown `--spaces` key warns, not errors** — `log.warning("space_not_in_mappings")` after pre-flight when a space key has no matching prefix entries

### Regression (US-001 preserved)

- [ ] **TC-001 baseline passes** — `pytest tests/ -v` → confirm `test_sync.py` (8 tests) and `test_confluence_client.py` (7 tests) still pass
- [ ] **Legacy `space_key` config accepted** — `.docsync.yml` with only `space_key: DOCS` loads without modification
- [ ] **No pre-flight when single-space** — `SyncEngine` initialized without `space_router` → `check_space_access` not called (`tests/test_sync_spaces.py::TestLegacySingleSpaceMode::test_legacy_engine_works_without_router`)

### Security

- [ ] **NFR-01 No hardcoded secrets** — `grep -rn "CONFLUENCE_API_TOKEN\|CONFLUENCE_USER\|GITHUB_TOKEN" src/docsync/` — values only via `os.environ`; no literals
- [ ] **New module `space_router.py`** — contains no HTTP calls, no credentials; pure routing logic
- [ ] **`check_space_access` error messages** — `SpaceAccessResult.error` contains only space key and HTTP status code; no auth headers or response bodies

### Test & Coverage

- [ ] **Run tests** — `pytest tests/ -v` → 83 passed, 0 failed
- [ ] **Check coverage** — `pytest tests/ --cov=src/docsync --cov-report=term-missing` → `space_router.py` 100%, overall ≥ 75%
- [ ] **Dry-run** — `docsync sync --dry-run --spaces DOCS --config .docsync.yml` → CLI accepts `--spaces` flag without error
