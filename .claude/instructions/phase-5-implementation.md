---
applyTo: "src/docsync/**"
---

# Instructions — Phase 5: Implementation

## Role
You are a developer implementing Python source code for DocSync. Execute the approved implementation plan exactly — implement all tasks in dependency order, run tests after each module, and enforce all design decisions.

## Implementation Order
Follow `docs/{TC_ID}/impl-plan.md` task ordering exactly:
1. Scaffolding first (no external dependencies)
2. Core models (config.py, __init__.py)
3. API clients (github_client.py, confluence_client.py)
4. Business logic (converter.py, sync.py)
5. CLI entrypoint (main.py)
6. GitHub Actions workflow
7. Tests (paired with each module)
8. Documentation (README.md last)

## Mandatory Coding Conventions
See `.claude/instructions/docsync.md` for the full coding ruleset. Key rules:
- `from __future__ import annotations` in every module
- `structlog` for all logging — no `print()`
- `RuntimeError` from HTTP clients; `FileNotFoundError` for GitHub 404
- All Confluence mutating calls wrapped with `@retry` from `tenacity`
- `find_page` uses `docsync:source_path` property (DD-01)
- Async GitHub calls with `asyncio.Semaphore(batch_size)` (DD-02)
- XHTML validation with lxml; fallback to code-block macro if invalid (DD-03)
- Secrets ONLY from `os.environ` — never hardcoded

## Design Decisions (Enforce All)

| ID | Decision | Where to Enforce |
|----|----------|-----------------|
| DD-01 | Page identity = `docsync:source_path` property | `confluence_client.find_page()` |
| DD-02 | Async httpx + `asyncio.Semaphore(batch_size)` | `github_client.fetch_files()` |
| DD-03 | XHTML validation with lxml; fallback to code macro | `converter.to_storage_format()` |
| DD-04 | Archive = Confluence trash (DELETE endpoint) | `confluence_client.archive_page()` |
| DD-05 | Sanitise HTTP exceptions before logging | Both client `except` blocks |

## Quality Gate (Must Pass Before Phase Complete)
Run after implementation:
```bash
pytest tests/ -v --tb=short
```
All tests must pass. Zero failures allowed.

```bash
python -m docsync.main sync --dry-run --config .docsync.yml
```
Must exit 0 (dry-run mode — no real API calls).

## File-by-File Checklist
- [ ] `src/docsync/__init__.py` — version, package exports
- [ ] `src/docsync/config.py` — pydantic v2 model, validated from env + YAML
- [ ] `src/docsync/github_client.py` — async, semaphore-batched, FileNotFoundError on 404
- [ ] `src/docsync/converter.py` — markdown2 + lxml XHTML validation
- [ ] `src/docsync/confluence_client.py` — find/create/update/archive with tenacity retry
- [ ] `src/docsync/sync.py` — orchestrates full sync pipeline
- [ ] `src/docsync/main.py` — click CLI (`sync` command, `--dry-run`, `--config`)
- [ ] `.github/workflows/docsync.yml` — triggered on push to main
- [ ] `tests/conftest.py` — shared fixtures (mock config, respx mocks)
- [ ] `tests/test_config.py`, `test_github_client.py`, etc. — one file per module

## Prohibited Behaviors
- Do NOT implement features beyond the approved implementation plan
- Do NOT use `print()` for logging
- Do NOT hardcode any secrets, tokens, or passwords
- Do NOT skip tests — every module needs unit tests
- Do NOT move to the next module if the current module's tests fail
