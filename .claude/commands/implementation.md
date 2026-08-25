---
description: "Phase 5 — Implement DocSync Python source code following the approved plan. Usage: /implementation TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# DocSync Phase 5 — Implementation

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are implementing the DocSync Automated Documentation Sync tool. Follow the task order in `docs/${testCase}/impl-plan.md` exactly.

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"4"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 4 (Implementation Planning) is not APPROVED.

## Mandatory Coding Conventions
- `from __future__ import annotations` in every module
- Full type annotations on all public APIs
- `structlog` for logging — no `print()` in library code
- `RuntimeError` from HTTP clients (tenacity matches it)
- `FileNotFoundError` for GitHub 404 responses
- Pydantic v2 for config validation (fail fast at startup)

## Enforce All Design Decisions
Read `docs/${testCase}/design-review.md` and implement every DD-XX decision:
- **DD-01**: `find_page` uses `docsync:source_path` Confluence property (NOT page title)
- **DD-02**: `GitHubClient` is fully async with `asyncio.Semaphore(batch_size)`
- **DD-03**: `convert()` returns `ConversionResult`; fallback to code-block macro if lxml parse fails
- **DD-04**: `archive_page` uses DELETE endpoint — 404 is swallowed (idempotent)
- **DD-05**: `_sanitised_error()` strips auth headers from logged exceptions

## After Each Module
Run: `pytest tests/test_{module_name}.py -v`
Fix any failing tests before proceeding to the next module.

## Quality Gate (Must Pass Before Reporting Complete)
```powershell
pytest tests/ -v          # 0 failures
docsync sync --dry-run --config .docsync.yml  # exits 0
```

## Context to Read
- `docs/${testCase}/impl-plan.md` — task order
- `docs/${testCase}/architecture.md` — component specs
- `docs/${testCase}/design-review.md` — design decisions
- `CLAUDE.md` — coding conventions

## Save & Archive
After all modules are implemented and quality gate passes:
1. Write an implementation summary to `outputs/${testCase}/phase-5-implementation/output.md`:
   - List every file created/modified in `src/docsync/` and `tests/`
   - Include final pytest pass/fail counts
   - Note any deviations from `docs/${testCase}/impl-plan.md`
2. Write `outputs/${testCase}/phase-5-implementation/agent-log.json`
3. Update `outputs/${testCase}/phase-status.json` → `phases."5".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 5: Implementation          ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Modules written: [list src/docsync/*.py]          ║
║  • Tests written: [list tests/*.py]                  ║
║  • pytest result: [X passed, 0 failed]               ║
║  • Dry-run result: [PASS / FAIL]                     ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 5 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 5 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
