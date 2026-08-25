# Requirements — DocSync Automated Documentation Sync

---

## US-001: Auto-sync GitHub Markdown to Confluence on push to main

**User Story**
As a development team member, I want markdown documentation files in GitHub repositories to automatically sync to our Confluence wiki whenever code changes are pushed, so that our docs are always up-to-date without manual effort.

**Agent Clarification Q&A**

> **Q:** Should sync be bidirectional (GitHub ↔ Confluence) or one-directional?
> **A:** One-directional: GitHub is the source of truth. Markdown files push to Confluence.

> **Q:** Which Confluence space(s) should receive synced content, and how does a repo page map to a Confluence page?
> **A:** Each repo gets its own Confluence space. Folder structure in the repo maps to parent/child Confluence page hierarchy.

> **Q:** What triggers the sync — push to any branch, or only to `main`/`master`?
> **A:** Only merges to `main`. Draft PR branches must not trigger syncs.

> **Q:** Should deleted markdown files remove the corresponding Confluence page?
> **A:** Yes — deletion in `main` should archive (not permanently delete) the Confluence page.

> **Q:** How should images and attachments embedded in markdown be handled?
> **A:** Upload images as Confluence attachments; rewrite relative `![img](path)` links to Confluence attachment URLs.

### Functional Requirements

| ID    | Requirement |
|-------|-------------|
| FR-01 | The system SHALL detect changes to `.md` files on push to `main` branch via GitHub Actions. |
| FR-02 | The system SHALL convert Markdown content to Confluence Storage Format (XHTML). |
| FR-03 | The system SHALL create a new Confluence page if no matching page exists for a given file path. |
| FR-04 | The system SHALL update an existing Confluence page when the source markdown file changes. |
| FR-05 | The system SHALL archive a Confluence page when the corresponding markdown file is deleted from `main`. |
| FR-06 | The system SHALL upload inline images as Confluence attachments and rewrite their URLs in the page body. |
| FR-07 | The system SHALL preserve the folder-to-page-hierarchy mapping (e.g., `docs/api/overview.md` → `API > Overview`). |
| FR-08 | The system SHALL produce a structured sync log (JSON lines) recording each file's sync outcome. |
| FR-09 | The system SHALL support a `--dry-run` CLI flag that previews changes without writing to Confluence. |
| FR-10 | The system SHALL expose a CLI entry point `docsync` for local and CI use. |
| FR-11 | The system SHALL report sync results as a GitHub Actions step summary. |
| FR-12 | The system SHALL support configuration via a `.docsync.yml` file at the repository root. |

### Non-Functional Requirements

| ID     | Requirement |
|--------|-------------|
| NFR-01 | **Security** — Confluence API token and GitHub token MUST be supplied via environment variables; never hard-coded or logged. |
| NFR-02 | **Performance** — Sync of up to 200 changed files MUST complete within 5 minutes on a standard GitHub Actions runner. |
| NFR-03 | **Reliability** — Transient Confluence API failures MUST be retried up to 3 times with exponential back-off before failing the job. |
| NFR-04 | **Observability** — Each sync run MUST emit a structured JSON-lines log and a human-readable GitHub Actions step summary. |
| NFR-05 | **Portability** — The tool MUST run on Python 3.10+ and be installable via `pip`. |
| NFR-06 | **Testability** — All external API calls MUST be abstracted behind interfaces to allow unit testing without live credentials. |
| NFR-07 | **Idempotency** — Running the sync twice on the same commit MUST produce no change on the second run (no duplicate pages or duplicate uploads). |
| NFR-08 | **Configurability** — Space key, root page ID, file include/exclude globs, and base URL MUST be configurable in `.docsync.yml`. |

### Constraints & Assumptions (US-001)
- Confluence Cloud REST API v2
- GitHub Actions as the CI/CD runtime
- Python 3.10+ runtime
- Markdown dialect: CommonMark with GitHub Flavored Markdown extensions

### Out of Scope (US-001)
- Bidirectional sync (Confluence → GitHub)
- Non-markdown files (PDFs, Word docs, images as top-level content)
- Jira ticket linking
- Multiple spaces per repository (addressed in US-002)

---

## US-002: `--spaces` flag to restrict sync to specific Confluence spaces  *(TC-002)*

**User Story**
As a developer, I want the DocsSync CLI to support a `--spaces` flag that restricts sync to specific Confluence spaces, so teams can isolate their documentation by space key and avoid unintended cross-space side-effects.

**Agent Clarification Q&A**

> **Q1 — Scope:** Should `--spaces` accept a single space key or a comma-separated list? If a file is already synced to a space NOT in `--spaces`, should it be left alone or archived?
> **A:** Comma-separated list. Files in spaces not listed are left alone — no accidental archival.

> **Q2 — Precedence:** When `--spaces` is passed on the CLI, does it override `space_key` in `.docsync.yml`, or add to it?
> **A:** CLI `--spaces` completely overrides `space_key`/`space_keys` in `.docsync.yml` for that run.

> **Q3 — Routing:** With multiple spaces, how does the tool know which files go to which space?
> **A:** Folder-to-space mappings in config (`space_mappings` block). `--spaces` restricts execution only to folders mapped to the listed spaces.

> **Q4 — Config:** Should `space_key` expand to a list? Must legacy single `space_key` still work?
> **A:** Yes — add `space_keys` list support. Legacy single `space_key: DOCS` must continue to parse without modification.

> **Q5 — Error handling:** If a specified space key doesn't exist in Confluence — fail entirely or skip?
> **A:** Fail entire run and exit immediately, unless `--continue-on-error` is explicitly passed.

> **Q6 — Security:** Pre-flight permission check before sync starts?
> **A:** Yes — validate read/write permissions on all target spaces before any file is modified; fail-fast on the first insufficient authorization.

### Functional Requirements

| ID    | Requirement |
|-------|-------------|
| FR-13 | The system SHALL accept a `--spaces` CLI flag that takes a comma-separated list of Confluence space keys (e.g. `--spaces DOCS,ENG`). |
| FR-14 | When `--spaces` is provided on the CLI, the system SHALL use only those space keys for that run, completely overriding any `space_key` or `space_keys` value in `.docsync.yml`. |
| FR-15 | The system SHALL support a `space_mappings` configuration block in `.docsync.yml` that maps repository folder prefixes to Confluence space keys (e.g. `docs/: DOCS`, `engineering/: ENG`). |
| FR-16 | When `--spaces` is specified, the system SHALL sync only the files whose configured `space_mappings` entry resolves to one of the provided space keys; files mapped to other spaces SHALL be skipped. |
| FR-17 | The system SHALL NOT archive, update, or create Confluence pages in spaces not listed in the active `--spaces` value; those spaces SHALL remain entirely unchanged. |
| FR-18 | The system SHALL perform a pre-flight authorization check (read and write) against every target space key before beginning any sync operations. |
| FR-19 | The system SHALL fail the entire run and exit immediately if any target space key does not exist in Confluence or if the configured credentials lack sufficient permissions, unless `--continue-on-error` is also provided. |
| FR-20 | The system SHALL support a `--continue-on-error` CLI flag; when set, authorization or existence failures for individual spaces SHALL be logged as warnings, that space SHALL be skipped, and sync SHALL continue for the remaining spaces. |
| FR-21 | The system SHALL support a `space_keys` list field in `.docsync.yml` as the preferred multi-space configuration, while continuing to accept and correctly parse the legacy `space_key` (singular) string field for backward compatibility. |

### Non-Functional Requirements

| ID     | Requirement |
|--------|-------------|
| NFR-09 | **Performance** — Pre-flight authorization checks for up to 10 target spaces SHALL complete within 10 seconds on a standard GitHub Actions runner. |
| NFR-10 | **Backward Compatibility** — Existing `.docsync.yml` files using the single `space_key` field SHALL continue to function without modification after upgrading. |
| NFR-11 | **Observability** — The sync log SHALL record the Confluence space key each page was synced to; pre-flight validation results (pass/fail per space) SHALL be included in the GitHub Actions step summary. |
| NFR-12 | **Error Clarity** — When a space key is not found or is unauthorized, the error message SHALL name the specific failing space key and the HTTP status code returned by the Confluence API. |

### Constraints & Assumptions (US-002)
- All target spaces use the same `CONFLUENCE_API_TOKEN` / `CONFLUENCE_USER` credentials — per-space authentication is out of scope.
- `space_mappings` entries are prefix-matched (longest-prefix wins if a file path could match multiple entries).
- The `--spaces` value is validated against `space_mappings` keys at startup; an unmapped space key is treated as an error.

### Out of Scope (US-002)
- Syncing a single markdown file to multiple spaces simultaneously.
- Dynamic space discovery (all target spaces must be explicitly named in config or `--spaces`).
- Per-space authentication credentials.
- Confluence Server / Data Center (Cloud API v2 only).
