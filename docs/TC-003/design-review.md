# Design Review — TC-003: Sync Summary Report

**Reviewer:** Senior Engineer (sdlc-design-review)
**Architecture doc:** docs/TC-003/architecture.md
**Date:** 2026-08-05

---

## Review Summary

The architecture is well-scoped. It builds on existing dataclasses (`SyncReport`, `SyncResult`, `SyncStatus`) and does not introduce unnecessary new abstractions. Risk level is **LOW**.

---

## Findings

### PASS — Component Design
- Adding computed properties (`created_count`, `updated_count`, `archived_count`, `skipped_count`, `error_count`) to `SyncReport` is clean and backward-compatible.
- Retaining `success_count`, `skip_count`, `failure_count` as aliases ensures no existing callers break.
- `summary_dict()` returns only safe numeric data and elapsed time — no secrets, no PII.

### PASS — Elapsed Time Capture
- `time.perf_counter()` is the correct choice: monotonic, stdlib, no side effects.
- Storing `elapsed_seconds` on `SyncReport` keeps it accessible both to `_print_summary()` and to callers/tests.

### PASS — CLI Flag Design
- `click.Choice(["table","json"])` provides compile-time validation; no arbitrary string injection possible.
- Default `"table"` preserves existing behaviour.

### PASS — Security
- JSON summary dict contains only integer counts and a float; no credential or path data leaks.
- Existing DD-05 (sanitise HTTP exceptions) already covers `SyncResult.error` fields.

### RISK-01 (LOW) — `elapsed_seconds` set after `asyncio.run()`
**Issue:** If `asyncio.run()` raises (pre-flight error), `elapsed_seconds` is never set.  
**Resolution (DD-TC003-01):** The `elapsed_seconds` field defaults to `0.0`; pre-flight errors exit via `sys.exit(1)` before `_print_summary()` is called, so the default is never displayed incorrectly.

### RISK-02 (LOW) — JSON serialisation fallback is silent
**Issue:** Architecture mentions falling back to table format if JSON serialisation fails, but `summary_dict()` only contains built-in Python types, so this can never realistically fail.  
**Resolution (DD-TC003-02):** Remove the fallback branch; rely on standard `json.dumps()`. If it does raise, let it propagate — it signals a programming error, not a user error.

### RISK-03 (TRIVIAL) — `--output-format` conflicts with JSON Lines from `report.log_jsonlines()`
**Issue:** `log_jsonlines()` already prints one JSON object per page. When `--output-format json` is used, both streams appear on stdout.  
**Resolution (DD-TC003-03):** `_print_summary()` is called *after* `report.log_jsonlines()`. The final JSON summary line is distinguishable because it contains aggregate keys (`created`, `updated`, etc.), not per-page keys (`path`, `status`). Document this in the `--output-format` help string. No structural change needed.

---

## Agreed Design Decisions

| ID | Decision |
|----|----------|
| DD-TC003-01 | `elapsed_seconds` defaults to `0.0`; pre-flight errors exit before `_print_summary()` so the default is never shown. |
| DD-TC003-02 | No JSON serialisation fallback needed; `summary_dict()` is always serialisable. |
| DD-TC003-03 | `--output-format json` summary line appears after per-page JSON lines; aggregate keys distinguish the two streams. |
| DD-TC003-04 | `skip_count` and `failure_count` are kept as deprecated aliases on `SyncReport` to preserve backward compatibility. |

---

## Architecture Sign-Off

The architecture as written (with the minor clarifications in DD-TC003-01 through DD-TC003-04) is **APPROVED** for implementation planning.

No changes to `architecture.md` are required.
