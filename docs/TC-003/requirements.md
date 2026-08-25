# Requirements — TC-003: Sync Summary Report

## User Story
**US-003:** As a developer, I want `docsync sync` to print a summary report after each run showing how many pages were created, updated, archived, and skipped — so I can quickly confirm the sync completed as expected.

**Test Case:** TC-003

---

## Acceptance Criteria

### AC-001 — Summary Printed After Each Sync
**Given** a developer runs `docsync sync` (with or without `--dry-run`)
**When** the sync run completes (success or partial failure)
**Then** a summary report is printed to stdout showing counts for: created, updated, archived, skipped

### AC-002 — Counts Are Accurate
**Given** a sync run processes N Markdown files
**When** each file is processed (create/update/archive/skip)
**Then** the count for the corresponding action increments by 1, and the total of all counts equals N

### AC-003 — Zero Counts Are Shown
**Given** a category has no activity (e.g., nothing archived)
**When** the summary is printed
**Then** that category is still displayed with a count of 0

### AC-004 — Dry-Run Shows Expected Counts
**Given** the `--dry-run` flag is used
**When** the summary is printed
**Then** it is labelled as a dry-run and reflects what would have happened (no actual Confluence writes)

### AC-005 — Machine-Readable Output Flag
**Given** the developer passes `--output-format json`
**When** the sync completes
**Then** the summary is emitted as a single-line JSON object to stdout

### AC-006 — Non-Zero Exit on Errors
**Given** one or more pages fail to sync
**When** the summary is printed
**Then** the error count is included in the summary and the CLI exits with code 1

---

## Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL collect a running tally of pages created, updated, archived, skipped, and errored during each sync run. |
| FR-002 | The system SHALL print the summary report to stdout after all pages have been processed, before the CLI exits. |
| FR-003 | The system SHALL display all five counters (created, updated, archived, skipped, errored) even when their value is 0. |
| FR-004 | The system SHALL label the summary as `DRY-RUN SUMMARY` when invoked with `--dry-run`, and as `SYNC SUMMARY` otherwise. |
| FR-005 | The system SHALL support `--output-format json` which outputs the summary as a single-line JSON object `{"created":N,"updated":N,"archived":N,"skipped":N,"errors":N}` to stdout instead of the human-readable table. |
| FR-006 | The system SHALL exit with code 1 if the error counter is greater than 0 at the end of the run. |
| FR-007 | The system SHALL include the total elapsed time (in seconds, two decimal places) in the summary report. |
| FR-008 | The system SHALL record a `SyncResult` dataclass (or equivalent) returned from `sync.run()` that encapsulates all counters, so callers can inspect results programmatically. |

---

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | The summary report SHALL be printed within 50 ms of the last page operation completing. |
| NFR-002 | The JSON output produced by `--output-format json` SHALL be valid JSON parseable by `json.loads()` with no extra whitespace or trailing newlines beyond the single newline terminator. |
| NFR-003 | Counter collection SHALL add no more than 1 ms of overhead per page processed. |
| NFR-004 | The `SyncResult` dataclass SHALL be importable from `docsync.sync` without requiring any Confluence or GitHub credentials. |
| NFR-005 | The human-readable summary SHALL use structured log output via `structlog` at `INFO` level so it appears in log files if log capture is configured. |

---

## Constraints & Assumptions

- The summary is always printed to **stdout** (not stderr).
- The `--output-format` flag is optional; default is human-readable table.
- Skipped pages are those whose content hash has not changed since the last sync.
- Errored pages are those that raised an exception during Confluence API calls.
- The elapsed time counter starts when `sync.run()` is called and ends just before the summary is printed.
- Existing `sync.run()` signature may be extended but must remain backward-compatible.

---

## Out of Scope

- Writing the summary to a file on disk (only stdout).
- Sending summary notifications (email, Slack, etc.).
- Per-page breakdown in the summary (only aggregate counts).
- Retrying failed pages automatically based on the error count.
- CSV or XML output formats (only human-readable table and JSON).

---

## Open Questions

| # | Question | Answer |
|---|----------|--------|
| Q1 | Should `--output-format` be extendable to other formats (e.g., `table`, `json`)? | Scoped to `json` only for this story; `table` is the default. |
| Q2 | Should the summary also be written to the structured log output? | Yes — via structlog at INFO level (NFR-005). |
