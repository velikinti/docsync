# Implementation Plan — TC-003: Sync Summary Report

**Derived from:** docs/TC-003/architecture.md + docs/TC-003/design-review.md
**Date:** 2026-08-05

---

## Task List

| Task ID | Description | File(s) | Depends On | Priority |
|---------|-------------|---------|------------|----------|
| T-01 | Add `elapsed_seconds: float = 0.0` field to `SyncReport` | `sync.py` | — | P0 |
| T-02 | Add `created_count`, `updated_count`, `archived_count`, `skipped_count`, `error_count` computed properties to `SyncReport` | `sync.py` | T-01 | P0 |
| T-03 | Keep `skip_count` and `failure_count` as backward-compat aliases on `SyncReport` | `sync.py` | T-02 | P0 |
| T-04 | Add `summary_dict()` method to `SyncReport` | `sync.py` | T-02 | P0 |
| T-05 | Capture elapsed time in `SyncEngine.run()` using `time.perf_counter()` and store in `report.elapsed_seconds` | `sync.py` | T-01 | P0 |
| T-06 | Add `--output-format` option to `sync` CLI command (`click.Choice(["table","json"])`, default `"table"`) | `main.py` | — | P0 |
| T-07 | Implement `_print_summary(report, dry_run, output_format)` helper in `main.py` | `main.py` | T-04, T-06 | P0 |
| T-08 | Replace one-line summary `click.echo` in `sync` command body with call to `_print_summary()` | `main.py` | T-07 | P0 |
| T-09 | Update `sync` command exit logic: use `report.error_count > 0` (was `failure_count`) | `main.py` | T-08 | P0 |
| T-10 | Write unit tests for new `SyncReport` properties and `summary_dict()` | `tests/test_sync.py` | T-04 | P1 |
| T-11 | Write CLI integration tests for `--output-format table` and `--output-format json` | `tests/test_sync_summary.py` | T-08 | P1 |

---

## Dependency Graph

```
T-01 ─► T-02 ─► T-03
              ├─► T-04 ─► T-07 ─► T-08 ─► T-09
              └─► T-10
T-05 (needs T-01)
T-06 ─► T-07
T-11 (needs T-08)
```

---

## Task Details

### T-01 — Add `elapsed_seconds` to `SyncReport`
Add `elapsed_seconds: float = 0.0` to the `SyncReport` dataclass (after the existing `results` field). No constructor change needed since it has a default.

### T-02 — Per-action computed properties
```python
@property
def created_count(self) -> int:
    return sum(1 for r in self.results if r.status == SyncStatus.CREATED)

@property
def updated_count(self) -> int:
    return sum(1 for r in self.results if r.status == SyncStatus.UPDATED)

@property
def archived_count(self) -> int:
    return sum(1 for r in self.results if r.status == SyncStatus.ARCHIVED)

@property
def skipped_count(self) -> int:
    return sum(1 for r in self.results if r.status == SyncStatus.SKIPPED)

@property
def error_count(self) -> int:
    return sum(1 for r in self.results if r.status == SyncStatus.FAILED)
```

### T-03 — Backward-compat aliases
```python
@property
def skip_count(self) -> int:       # alias for skipped_count
    return self.skipped_count

@property
def failure_count(self) -> int:    # alias for error_count
    return self.error_count
```
Remove the existing `success_count`, `skip_count`, `failure_count` implementations and replace with the above (keep `success_count` as-is or redefine as `created_count + updated_count + archived_count`).

### T-04 — `summary_dict()`
```python
def summary_dict(self) -> dict:
    return {
        "created": self.created_count,
        "updated": self.updated_count,
        "archived": self.archived_count,
        "skipped": self.skipped_count,
        "errors": self.error_count,
        "elapsed_seconds": round(self.elapsed_seconds, 2),
    }
```

### T-05 — Elapsed time in `SyncEngine.run()`
```python
import time

def run(self, ...) -> SyncReport:
    start = time.perf_counter()
    report = asyncio.run(self._run_async(...))
    report.elapsed_seconds = time.perf_counter() - start
    return report
```

### T-06 — `--output-format` CLI flag
Add to the `sync` Click command decorator:
```python
@click.option(
    "--output-format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Summary output format after sync: table (default) or json",
)
```
Add `output_format: str` to the `sync()` function signature.

### T-07 — `_print_summary()` helper
```python
def _print_summary(report: SyncReport, dry_run: bool, output_format: str) -> None:
    import json as _json
    if output_format == "json":
        print(_json.dumps(report.summary_dict()), flush=True)
        return
    label = "DRY-RUN SUMMARY" if dry_run else "SYNC SUMMARY"
    log.info(
        label,
        created=report.created_count,
        updated=report.updated_count,
        archived=report.archived_count,
        skipped=report.skipped_count,
        errors=report.error_count,
        elapsed_seconds=round(report.elapsed_seconds, 2),
    )
    click.echo(f"\n[docsync] {'DRY RUN ' if dry_run else ''}SUMMARY")
    click.echo(f"  Created:  {report.created_count}")
    click.echo(f"  Updated:  {report.updated_count}")
    click.echo(f"  Archived: {report.archived_count}")
    click.echo(f"  Skipped:  {report.skipped_count}")
    click.echo(f"  Errors:   {report.error_count}")
    click.echo(f"  Elapsed:  {report.elapsed_seconds:.2f}s")
```

### T-08 — Replace one-liner in `sync` command
Remove:
```python
click.echo(
    f"[docsync] Done — {report.success_count} synced, "
    f"{report.skip_count} skipped, {report.failure_count} failed"
)
```
Add:
```python
_print_summary(report, dry_run, output_format)
```

### T-09 — Fix exit condition
```python
if report.error_count > 0:
    sys.exit(1)
```

### T-10 — Unit tests (`tests/test_sync.py`)
Add tests:
- `SyncReport` with mixed statuses returns correct per-action counts
- `summary_dict()` keys match spec, values correct, `elapsed_seconds` rounded to 2dp
- `skip_count` and `failure_count` aliases return same as `skipped_count` / `error_count`

### T-11 — CLI integration tests (`tests/test_sync_summary.py`)
Use `click.testing.CliRunner`:
- Table format: output contains `SUMMARY`, `Created:`, `Updated:`, `Archived:`, `Skipped:`, `Errors:`, `Elapsed:`
- JSON format: output contains valid JSON with keys `created`, `updated`, `archived`, `skipped`, `errors`, `elapsed_seconds`
- Dry-run flag: label shows `DRY RUN SUMMARY`
- Error count > 0: exit code is 1

---

## Estimated Sequence

1. T-01 → T-02 → T-03 → T-04 (sync.py dataclass changes)
2. T-05 (sync.py engine change)
3. T-06 → T-07 → T-08 → T-09 (main.py CLI changes)
4. T-10 (unit tests)
5. T-11 (integration tests)
