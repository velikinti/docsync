# PR Description — TC-003: Sync Summary Report

## Summary

Implements **US-003**: `docsync sync` now prints a structured summary report after every run, showing counts of pages created, updated, archived, skipped, and errored — plus elapsed time. An optional `--output-format json` flag enables machine-readable output for CI pipelines.

---

## Changes Made

### `src/docsync/sync.py`
- Added `import time`
- Added `elapsed_seconds: float = 0.0` field to `SyncReport`
- Added five computed properties: `created_count`, `updated_count`, `archived_count`, `skipped_count`, `error_count`
- Retained `success_count`, `skip_count`, `failure_count` as backward-compatible aliases (no breaking changes)
- Added `summary_dict()` → `dict` method for JSON-serialisable aggregate summary
- `SyncEngine.run()` captures elapsed wall time via `time.perf_counter()` and stores it in `report.elapsed_seconds`

### `src/docsync/main.py`
- Added `log = structlog.get_logger()` module-level logger
- Added `import json as _json` for JSON serialisation
- Added `SyncReport` to imports
- Added `--output-format` CLI option (`table` | `json`, default `table`)
- Added `_print_summary(report, dry_run, output_format)` helper
- Replaced one-line "Done —" echo with `_print_summary()` call
- Exit condition updated to `report.error_count > 0`

### `tests/test_sync_summary.py` *(new)*
- 19 tests covering all counter properties, backward-compat aliases, `summary_dict()`, CLI table/JSON output, dry-run label, and exit codes

---

## Example Output

### Default (table format)
```
[docsync] Syncing commit a1b2c3d4 (acme/docs)

[docsync] SUMMARY
  Created:  3
  Updated:  1
  Archived: 0
  Skipped:  2
  Errors:   0
  Elapsed:  1.43s
```

### `--output-format json`
```json
{"created": 3, "updated": 1, "archived": 0, "skipped": 2, "errors": 0, "elapsed_seconds": 1.43}
```

### `--dry-run`
```
[docsync] DRY RUN SUMMARY
  Created:  3
  ...
```

---

## Test Evidence

| Suite | Tests | Result |
|-------|-------|--------|
| `test_sync_summary.py` (new) | 19 | ✅ All pass |
| Full suite | 102 | ✅ All pass (0 regressions) |
| Coverage (total) | — | 84% |

---

## Known Limitations

- Per-page breakdown is not included in the summary (aggregate counts only) — per out-of-scope decision.
- Only `table` and `json` formats are supported (CSV/XML out of scope).

---

## Reviewer Checklist

- [ ] `SyncReport.summary_dict()` returns correct keys and types
- [ ] `--output-format json` output is valid JSON parseable by `json.loads()`
- [ ] `--dry-run` label shows `DRY RUN SUMMARY`
- [ ] Exit code is 1 when `error_count > 0`
- [ ] Backward-compat aliases (`skip_count`, `failure_count`) work as before
- [ ] No new dependencies introduced
- [ ] All 102 tests pass
