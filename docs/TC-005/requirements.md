# Requirements — Archive Confluence Pages on Source File Deletion

**User Story**
As a developer, I want DocSync to archive Confluence pages when their source Markdown files
are deleted from the GitHub repository, so that the Confluence space stays in sync with the
repo and stale pages are automatically cleaned up.

---

## Agent Clarification Q&A

> **Q1:** How does DocSync detect that a file has been deleted — via the GitHub push webhook
> payload, the Commits API, or by diffing repo state against Confluence?
>
> **A1:** Via `GitHubClient.list_changed_files()`, which calls the GitHub Commits API and maps
> `status: "removed"` entries to `ChangeType.DELETED`. No new detection mechanism is required.

> **Q2:** Should deletion tracking respect the same `include_globs` / `exclude_globs` filters
> defined in `.docsync.yml`, or should all `.md` file deletions trigger archiving?
>
> **A2:** Only files that pass the existing glob filter (`_matches_globs`) are eligible for
> archiving — consistent with how additions and modifications are handled.

> **Q3:** What should happen when a deleted file has no corresponding Confluence page (e.g.,
> the file was added and deleted before DocSync ever synced it)?
>
> **A3:** Emit a structured `structlog.warning("page_not_found_for_delete", path=...)` and
> record the result as `SyncStatus.SKIPPED`. No exception should be raised.

> **Q4:** Should pages be moved to Confluence trash (recoverable) or permanently deleted?
>
> **A4:** Archived to Confluence trash (recoverable), using the existing `archive_page()` DELETE
> endpoint — consistent with DD-04. Hard deletes are out of scope.

> **Q5:** Should this behaviour be opt-in or always-on? Could teams accidentally lose pages
> they did not intend to remove?
>
> **A5:** Controlled by a new `archive_on_delete` boolean field in `DocSyncConfig` (default:
> `true`). Setting it to `false` skips all archiving for deletion events and emits a debug log,
> giving cautious teams an escape hatch.

> **Q6:** How should renamed files be handled? GitHub represents a rename as a single
> `renamed` entry with `previous_filename`.
>
> **A6:** A `ChangeType.RENAMED` file SHALL be treated as: archive the previous path + upsert
> the new path, within the same sync run. This mirrors what a delete + add in a single commit
> would do.

---

## Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | The system SHALL detect file deletions by reading `ChangeType.DELETED` entries returned by `GitHubClient.list_changed_files()` from the GitHub Commits API. |
| FR-02 | The system SHALL apply `include_globs` and `exclude_globs` filters to deleted file paths; paths that do not satisfy `_matches_globs()` SHALL be excluded from archiving. |
| FR-03 | The system SHALL locate the corresponding Confluence page for a deleted path by querying the `docsync:source_path` content property via `ConfluenceClient.find_page_by_property()`. |
| FR-04 | The system SHALL archive the located Confluence page by calling `ConfluenceClient.archive_page()`, moving it to Confluence trash (recoverable; DD-04). |
| FR-05 | The system SHALL record each successfully archived page in `SyncReport` with `SyncStatus.ARCHIVED` and the resolved `page_id`. |
| FR-06 | The system SHALL emit `log.warning("page_not_found_for_delete", path=<path>)` and record `SyncStatus.SKIPPED` when no Confluence page exists for a deleted source path. |
| FR-07 | The system SHALL support a new `archive_on_delete` boolean field in `DocSyncConfig` (default: `true`). When `false`, deletion events SHALL be skipped with `SyncStatus.SKIPPED` and a `log.debug("archive_on_delete_disabled", path=<path>)` entry. |
| FR-08 | The system SHALL treat a GitHub `ChangeType.RENAMED` entry as: archive the `previous_path` (if a Confluence page exists for it) followed by upsert of the new `path`, within the same sync run. |
| FR-09 | The system SHALL skip all Confluence API calls for deletion events and return `SyncStatus.SKIPPED` when `DocSyncConfig.dry_run` is `true`. |
| FR-10 | The system SHALL support archiving directory-type pages: when the deleted path resolves to a page with `docsync:path_type = "directory"`, the system SHALL delegate to `HierarchyManager.archive_directory()` to recursively archive all child pages. |
| FR-11 | The system SHALL include archived page counts in `SyncReport.archived_count` and surface them in `SyncReport.summary_dict()` and the GitHub Actions Step Summary table. |

---

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | `ConfluenceClient.archive_page()` SHALL be decorated with the existing `_RETRY` tenacity policy: up to 3 attempts, exponential back-off (min 2 s, max 30 s), retrying on `RuntimeError`. |
| NFR-02 | Archiving a single page SHALL complete within 10 seconds per attempt under normal Confluence API conditions (< 500 ms round-trip network latency). |
| NFR-03 | No Confluence API tokens, user credentials, or raw HTTP response bodies containing secrets SHALL appear in any structlog output during delete operations (DD-05). |
| NFR-04 | The archive operation SHALL be idempotent: a 404 response from `DELETE /wiki/rest/api/content/{id}` SHALL be treated as success (page already absent), with no error raised and no retry triggered. |
| NFR-05 | Processing N deleted files in a single push event SHALL add no more than `N × 1 s` to total sync wall-clock time (assuming Confluence latency ≤ 500 ms per call). |

---

## Constraints & Assumptions

- **DD-01** — Page identity is `docsync:source_path` property. Title-based lookup is NOT used for archiving.
- **DD-04** — Archive = Confluence trash (soft delete). Permanent deletion is out of scope.
- **DD-05** — HTTP exceptions are sanitised before logging; `_sanitised_error()` is used for all Confluence calls.
- The GitHub Commits API is the authoritative source for the deleted-files list; DocSync does not maintain its own inventory.
- `ConfluenceClient.archive_page()` already implements the DELETE endpoint. No new HTTP method is required.
- Child-page archiving (for directory-type pages) is fully delegated to `HierarchyManager.archive_directory()`.
- The new `archive_on_delete` field must be backwards-compatible: existing `.docsync.yml` files that omit the field SHALL default to `true` (preserve current behaviour).

---

## Out of Scope

- Hard (permanent) deletion of Confluence pages.
- Restoring previously-archived pages when a deleted file is re-added to the repository.
- Detecting deletions through means other than the GitHub Commits API (e.g., direct push webhooks, full-tree repo diff).
- Archiving pages in Confluence spaces not configured in `.docsync.yml`.
- Notifying external systems (Slack, email, Jira) when a page is archived.
- UI or dashboard changes to surface archived-page counts to end users.
