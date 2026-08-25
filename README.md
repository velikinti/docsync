# DocSync — Automated GitHub Markdown → Confluence Sync

Automatically syncs markdown documentation from GitHub repositories to Confluence Cloud on every merge to `main`.

## Features

- Detects changed `.md` files via GitHub Actions on push to `main`
- Converts GitHub Flavored Markdown to Confluence Storage Format
- Creates, updates, or archives Confluence pages to mirror repo structure
- Uploads inline images as Confluence attachments
- Idempotent — safe to re-run on the same commit
- `--dry-run` preview mode
- Structured JSON-lines log + GitHub Actions step summary

## Quick Start

### 1. Add GitHub Secrets

In your repository → Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|-------|
| `CONFLUENCE_API_TOKEN` | Your Confluence API token |
| `CONFLUENCE_USER` | Your Confluence account email |

### 2. Add `.docsync.yml` to your repo root

```yaml
confluence_base_url: https://your-org.atlassian.net
space_key: DOCS
root_page_id: "123456"   # ID of the parent Confluence page
docs_root: docs          # repo folder to sync
include_globs:
  - "docs/**/*.md"
  - "README.md"
exclude_globs:
  - "docs/drafts/**"
batch_size: 10
```

### 3. The workflow runs automatically

Push any `.md` file to `main` and the GitHub Actions workflow (`.github/workflows/docsync.yml`) will sync it to Confluence.

---

## Local Development

### Install

```bash
pip install -e ".[dev]"
```

### Set environment variables

```bash
export CONFLUENCE_API_TOKEN=your_token
export CONFLUENCE_USER=your@email.com
export GITHUB_TOKEN=ghp_your_token
export GITHUB_REPOSITORY_OWNER=your-org
export GITHUB_REPOSITORY_NAME=your-repo
export GITHUB_SHA=abc123def456
```

### Preview without writing (dry run)

```bash
docsync sync --dry-run --config .docsync.yml
```

### Full sync

```bash
docsync sync --config .docsync.yml
```

---

## Configuration Reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `confluence_base_url` | string | required | Base URL of your Confluence Cloud instance |
| `space_key` | string | required | Confluence space key (e.g. `DOCS`) |
| `root_page_id` | string | required | Page ID to use as parent for top-level docs |
| `docs_root` | string | `docs` | Repo-relative folder to sync |
| `include_globs` | list | `["**/*.md"]` | Glob patterns to include |
| `exclude_globs` | list | `[]` | Glob patterns to exclude |
| `batch_size` | int | `10` | Concurrent GitHub API fetch limit (1–50) |
| `dry_run` | bool | `false` | Preview mode — no writes to Confluence |

---

## Project Structure

```
.github/
  workflows/docsync.yml      # GitHub Actions trigger
  prompts/                   # GitHub Copilot prompt files
  instructions/              # GitHub Copilot coding instructions
docs/                        # SDLC artifacts (requirements, architecture, etc.)
src/docsync/
  config.py                  # Pydantic config model
  github_client.py           # Async GitHub REST client
  converter.py               # Markdown → Confluence Storage Format
  confluence_client.py       # Confluence REST client with retry
  sync.py                    # SyncEngine orchestrator
  main.py                    # CLI entry point
tests/                       # Pytest test suite
.docsync.yml                 # Example configuration
```

---

## Running Tests

```bash
pytest tests/ -v --tb=short
```

With coverage:

```bash
pytest tests/ --cov=src/docsync --cov-report=term-missing
```

---

## SDLC Artifacts

All SDLC phase documents are in `docs/`:

| Phase | File |
|-------|------|
| Requirements | `docs/requirements.md` |
| Architecture | `docs/architecture.md` |
| Design Review | `docs/design-review.md` |
| Implementation Plan | `docs/impl-plan.md` |
| Code Review | `docs/code-review.md` |

---

## Known Limitations (v1)

- One-directional sync only (GitHub → Confluence)
- Images must be relative paths in the repo (not URLs to external services)
- Mermaid diagrams are not rendered — converted as code blocks
- Confluence pages deleted outside the tool are not auto-restored
- Single Confluence instance per repo configuration
