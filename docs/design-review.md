# Design Review — US-002: `--spaces` flag  *(TC-002)*

Reviewer: sdlc-design-review agent
Input: `docs/requirements.md` (FR-13..FR-21, NFR-09..NFR-12), `docs/architecture.md` (US-002 section)

---

## 1. Requirements Coverage Check

| FR/NFR | Requirement summary | Architecture coverage | Status |
|--------|--------------------|-----------------------|--------|
| FR-13 | `--spaces` CLI flag, comma-separated | `main.py` click option; `resolve_active_spaces()` | PASS |
| FR-14 | `--spaces` overrides config entirely | `resolve_active_spaces(cli_override)` returns early if set | PASS |
| FR-15 | `space_mappings` in `.docsync.yml` | `DocSyncConfig.space_mappings: Dict[str, str]` | PASS |
| FR-16 | Sync only files whose mapped space is in `--spaces` | `SpaceRouter.resolve()` + engine filter | PASS |
| FR-17 | Non-listed spaces left unchanged | Engine skips files with unmatched space; no archive calls | PASS |
| FR-18 | Pre-flight auth check on all target spaces | `check_space_access()` before any writes | PASS |
| FR-19 | Fail entire run if any space missing/unauthorized | RuntimeError in pre-flight unless `--continue-on-error` | PASS |
| FR-20 | `--continue-on-error` flag | click flag; engine drops failed spaces from active list | PASS |
| FR-21 | `space_keys` list + legacy `space_key` compat | `coerce_space_key` validator promotes legacy field | PASS |
| NFR-09 | Pre-flight for 10 spaces < 10 s | 10 x ~200 ms sequential = ~2 s -- within budget | PASS |
| NFR-10 | Legacy `.docsync.yml` unchanged | Validator auto-promotes -- no user action needed | PASS |
| NFR-11 | Log records space key per page; step summary includes pre-flight | `SyncResult.space_key`; step summary extended | PASS |
| NFR-12 | Error message names failing space + HTTP status | `SpaceAccessResult.error` includes both | PASS |

**Coverage: 13/13 -- all requirements addressed.**

---

## 2. Risks Identified

### RISK-06 -- Unmapped file silently skipped (MEDIUM)
**Description:** If a changed file has no matching prefix in `space_mappings`, it is silently skipped. A developer adding a new top-level folder and forgetting to add a mapping gets no sync and no CI failure.

**Mitigation:** Engine emits WARNING-level log for every unmapped file, and the GitHub Actions step summary lists all such files in a dedicated "Attention" section. No run failure (too noisy for large repos), but the warning must be visible.

**Architecture update required:** distinct `error` string `"no space_mapping for path"`; step summary groups these separately.

### RISK-07 -- Pre-flight check races with sync (LOW)
**Description:** Auth is verified pre-flight, but a permission could be revoked between the check and the actual write (TOCTOU window).

**Mitigation:** Acceptable -- transient 403s during sync are caught by existing `tenacity` retry. Document as a known limitation. No architecture change needed.

### RISK-08 -- `space_mappings` prefix collision (LOW)
**Description:** Keys like `"docs"` and `"docs/"` are ambiguous for a file at `docs/foo.md`.

**Mitigation:** `SpaceRouter.__init__` normalises all keys by appending `/` if missing. Document that keys are folder prefixes.

**Architecture update required:** normalisation in `SpaceRouter.__init__`.

### RISK-09 -- Empty `--spaces` argument (LOW)
**Description:** `--spaces ""` produces `[""]` after split, triggering a confusing pre-flight failure.

**Mitigation:** CLI validates `--spaces` is non-empty after strip; raises `click.BadParameter` before loading config.

---

## 3. Gaps Identified

### GAP-04 -- No validation that `--spaces` keys exist in `space_mappings`
**Description:** Passing `--spaces XYZ` when `XYZ` has no mapped folders results in all files skipping with no error.

**Resolution:** After resolving `active_spaces`, warn for any space not appearing as a value in `space_mappings`: *"Space XYZ is in --spaces but has no entries in space_mappings -- no files will sync to it."*

### GAP-05 -- `SyncReport` not updated for multi-space aggregation
**Description:** `SyncReport.success_count` etc. are global. Step summary needs per-space breakdown (NFR-11) but `SyncReport` has no grouping.

**Resolution:** Add `SyncReport.by_space() -> Dict[str, List[SyncResult]]` method. Step summary writer calls it to render the per-space table.

---

## 4. Design Decisions Confirmed

| ID | Decision | Verdict |
|----|----------|---------|
| DD-06 | Longest-prefix matching | CONFIRMED + key normalisation per RISK-08 |
| DD-07 | `--spaces` is total override | CONFIRMED |
| DD-08 | Pre-flight before any writes | CONFIRMED |
| DD-09 | `--continue-on-error` skips spaces not files | CONFIRMED |
| DD-10 | Auto-promote `space_key` to `space_keys` | CONFIRMED |
| DD-11 | Unmapped files emit WARNING + appear in step summary "Attention" section | NEW |
| DD-12 | `space_mappings` keys normalised to trailing `/` in `SpaceRouter.__init__` | NEW |
| DD-13 | `--spaces` values not in `space_mappings` produce a warning, not an error | NEW |

---

## 5. Architecture Updates Required Before Implementation

1. `SpaceRouter.__init__`: normalise all mapping keys -- `key if key.endswith("/") else key + "/"`.
2. `SyncReport`: add `by_space() -> Dict[str, List[SyncResult]]` grouping method.
3. `SyncEngine`: log WARN (not INFO) for files skipped with `"no space_mapping for path"`.
4. `main.py` CLI: validate `--spaces` non-empty after strip; warn if any space not in `space_mappings` values.
5. Step summary: add "Unmapped files" section listing all SKIPPED-due-to-no-mapping paths.

---

## 6. Overall Verdict

**APPROVED WITH CHANGES**

The architecture covers all 13 requirements. Five targeted updates (above) must be incorporated into the implementation plan. No requirement gaps remain after GAP-04 and GAP-05 resolutions.
