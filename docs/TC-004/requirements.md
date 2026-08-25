# Requirements — TC-004: Nested Directory Structure as Parent-Child Confluence Pages

## User Story
**US-004:** As a developer, I want `docsync sync` to mirror the GitHub repo directory structure as nested parent-child Confluence pages, so that `docs/api/auth.md` creates a child page under an `api` parent — while respecting `--spaces` filtering, emitting a sync summary, supporting `--dry-run`, retrying on transient failures, uploading inline images, archiving deleted files at any depth, and logging all operations as JSON-lines.

**Test Case:** TC-004

---

## Agent Clarification Q&A

> **Q1 — Hierarchy depth:** How many levels of nesting should be supported — is there a maximum depth, or should the tool mirror any depth present in the repo?
> **A:** No maximum — mirror any depth present in the repo (unlimited nesting).

> **Q2 — Intermediate directories with no `.md` file:** If `docs/api/` exists only as a container folder (no `index.md` or `README.md`), should a Confluence parent page still be created for it? If so, what should its title and content be?
> **A:** Yes — create an empty parent page titled after the directory name (e.g., `api`). Body can be empty or a short auto-generated placeholder.

> **Q3 — Root anchor:** What is the root parent page in Confluence to which top-level files/folders attach? Is it the space root, or a configured page ID?
> **A:** A configurable `root_page_id` in `.docsync.yml`; the tool attaches all top-level content as children of that page.

> **Q4 — Renaming/moving files:** If `docs/api/auth.md` is moved to `docs/security/auth.md`, should the old page be archived and a new page created, or should the existing page be moved in Confluence?
> **A:** Archive the old page (move it to trash) and create a new page at the new path. No Confluence page-move operations.

> **Q5 — Page identity across renames:** How does the system identify an existing Confluence page — by title, by a stored `docsync:source_path` property, or something else?
> **A:** By the `docsync:source_path` custom property (consistent with DD-01). Title changes are allowed; path is canonical.

> **Q6 — Archiving depth:** If a parent directory is deleted from the repo, should all its descendant pages be archived recursively?
> **A:** Yes — archiving a directory archives all descendant pages at every depth.

---

## Acceptance Criteria

### AC-001 — Nested Page Creation
**Given** a repo contains `docs/api/auth.md`
**When** `docsync sync` runs
**Then** a Confluence page for `auth.md` is created as a child of an `api` parent page, which is itself a child of the configured `root_page_id`

### AC-002 — Intermediate Directory Pages
**Given** `docs/api/` exists in the repo with no `index.md`
**When** `docsync sync` runs
**Then** an empty placeholder parent page titled `api` is created in Confluence

### AC-003 — Archive on File Delete
**Given** `docs/api/auth.md` was previously synced
**When** the file is deleted from the `main` branch
**Then** the corresponding Confluence page is archived (trashed), not permanently deleted

### AC-004 — Recursive Archive on Directory Delete
**Given** the entire `docs/api/` directory is deleted from `main`
**When** `docsync sync` runs
**Then** all descendant Confluence pages (including intermediate parents) are archived

### AC-005 — Path Move = Archive + Create
**Given** `docs/api/auth.md` is moved to `docs/security/auth.md`
**When** `docsync sync` runs
**Then** the old Confluence page is archived and a new page is created under the `security` parent

### AC-006 — `--dry-run` Produces No Writes
**Given** `--dry-run` is passed
**When** `docsync sync` runs
**Then** no Confluence pages are created, updated, or archived; the expected operations are logged only

### AC-007 — `--spaces` Filtering Respected
**Given** `--spaces ENG` is passed and a file maps to the `DOCS` space
**When** `docsync sync` runs
**Then** the `DOCS`-mapped file is skipped; no page is created/updated in `DOCS`

### AC-008 — Inline Images Uploaded
**Given** a markdown file contains `![diagram](./images/arch.png)`
**When** the page is created or updated
**Then** `arch.png` is uploaded as a Confluence attachment and the body references the attachment URL

### AC-009 — JSON-Lines Log
**Given** a sync run completes
**Then** each file operation is recorded as a JSON-lines entry in the configured log output

### AC-010 — Retry on Transient Failures
**Given** a Confluence API call returns HTTP 429 or 5xx
**When** the error occurs
**Then** the system retries up to 3 times with exponential back-off before marking the page as errored

---

## Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-001 | The system SHALL mirror the GitHub repository directory structure as a nested parent-child Confluence page hierarchy to unlimited depth. |
| FR-002 | The system SHALL create an intermediate Confluence parent page (with placeholder body) for every directory segment in a file's path that does not already have a corresponding Confluence page. |
| FR-003 | The system SHALL attach all top-level files and directories as children of the `root_page_id` configured in `.docsync.yml`. |
| FR-004 | The system SHALL identify each Confluence page by its `docsync:source_path` custom property (the repo-relative file or directory path), not by title. |
| FR-005 | The system SHALL create a new Confluence page as a child of the correct parent when a new markdown file is detected. |
| FR-006 | The system SHALL update an existing Confluence page (matched by `docsync:source_path`) when its source markdown content changes. |
| FR-007 | The system SHALL archive (move to Confluence trash, `status: trashed`) the Confluence page whose `docsync:source_path` matches a deleted markdown file. |
| FR-008 | The system SHALL recursively archive all descendant Confluence pages when a directory is deleted from the repository. |
| FR-009 | The system SHALL archive the old Confluence page and create a new page at the new path when a markdown file is moved (path change detected). |
| FR-010 | The system SHALL upload inline images referenced in markdown as Confluence attachments on the same page, and rewrite image references in the page body to the Confluence attachment URL. |
| FR-011 | The system SHALL emit a JSON-lines log entry for every file operation (create, update, archive, skip, error) containing at minimum: `timestamp`, `action`, `source_path`, `confluence_page_id`, `space_key`. |
| FR-012 | The system SHALL retry any Confluence API call that returns HTTP 429 or 5xx up to 3 times using exponential back-off before recording the operation as an error. |
| FR-013 | The system SHALL support `--dry-run` mode in which no Confluence pages are created, updated, archived, or modified, but all planned operations are logged. |
| FR-014 | The system SHALL respect `--spaces` filtering: files whose `space_mappings` entry resolves to a space key not listed in `--spaces` SHALL be skipped without error. |
| FR-015 | The system SHALL emit a sync summary after each run showing counts for: created, updated, archived, skipped, errored — consistent with US-003 / FR-001 through FR-008 in TC-003. |
| FR-016 | The system SHALL support `root_page_id` as a configurable field in `.docsync.yml` per space mapping entry. |

---

## Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-001 | **Performance** — Building and traversing the full page hierarchy for a repo with up to 500 markdown files SHALL complete within 60 seconds on a standard GitHub Actions runner. |
| NFR-002 | **Idempotency** — Running `docsync sync` twice on the same commit SHALL produce no changes on the second run; no duplicate intermediate parent pages SHALL be created. |
| NFR-003 | **Reliability** — Retry logic SHALL use exponential back-off with a base delay of 1 second, doubling each attempt, capped at 30 seconds. |
| NFR-004 | **Observability** — Every JSON-lines log entry SHALL be valid JSON parseable by `json.loads()` with no extra whitespace beyond the newline terminator. |
| NFR-005 | **Security** — No Confluence API token, GitHub token, or user credentials SHALL appear in any log entry, page body, or error message. |
| NFR-006 | **Testability** — All hierarchy-building and page-parenting logic SHALL be unit-testable without live Confluence or GitHub credentials (mock-friendly interfaces). |
| NFR-007 | **Backward Compatibility** — Existing `.docsync.yml` files that do not specify `root_page_id` SHALL continue to work, defaulting to the configured space root. |
| NFR-008 | **Depth Correctness** — The parent-child relationship in Confluence SHALL exactly match the directory depth in the repository for every processed file. |

---

## Constraints & Assumptions

- GitHub is the source of truth; Confluence content is never read back to update GitHub.
- Only push events to `main` branch trigger sync.
- Markdown dialect: CommonMark with GitHub Flavored Markdown extensions.
- Confluence Cloud REST API v2.
- The same `CONFLUENCE_API_TOKEN` / `CONFLUENCE_USER` credentials are used for all spaces.
- Intermediate parent pages created for directories have an empty body unless the directory contains an `index.md` or `README.md`, in which case that file's content is used.
- `docsync:source_path` custom page property is the canonical page identity mechanism (DD-01).

---

## Out of Scope

- Moving Confluence pages using the Confluence move-page API (archive + create is used instead).
- Bidirectional sync (Confluence → GitHub).
- Non-markdown files as first-class pages (images are attachments only).
- Per-space authentication credentials.
- Confluence Server / Data Center (Cloud API v2 only).
- Generating a visual sitemap or table of contents page.
- Real-time (webhook-based) sync from GitHub; only push-to-main via GitHub Actions is in scope.
