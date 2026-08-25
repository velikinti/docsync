---
description: "Phase 4 — Break approved architecture into a prioritized implementation task list. Usage: /impl-planning TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
---

# DocSync Phase 4 — Implementation Planning

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are a technical lead for the DocSync project. Break down the approved architecture into a concrete, dependency-ordered implementation plan. The implementation agent executes tasks in the exact order you specify.

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"3"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 3 (Design Review) is not APPROVED.

## Planning Principles
- **Dependency-first ordering**: No task should reference components that don't exist yet
- **Test pairing**: Every implementation task T-XX must have a paired test task
- **P0 completeness**: P0 tasks must form a complete critical path (no orphans)
- **Concrete descriptions**: Task descriptions must name the specific file and function to implement
- **Realistic estimates**: Think through what each task involves

## Task Granularity
- Completable in 15–90 minutes
- A single logical unit (one module, one test file, one workflow)
- Independently testable

## Output: `docs/${testCase}/impl-plan.md`

### Task Breakdown
Organize into phases:
- Phase 0: Scaffolding (directory structure, setup.py, requirements.txt, config example)
- Phase 1: Core models & config (config.py, __init__.py)
- Phase 2: GitHub client (github_client.py)
- Phase 3: Markdown converter (converter.py)
- Phase 4: Confluence client (confluence_client.py)
- Phase 5: Sync engine (sync.py)
- Phase 6: CLI entry point (main.py)
- Phase 7: GitHub Actions workflow
- Phase 8: Integration, tests & docs

Each task:
| Task | Description | File(s) | Depends On | Priority | Estimate |

Priorities: P0 (blocking), P1 (core), P2 (enhancement)
Estimates: 15min / 30min / 45min / 60min / 90min

### Dependency Graph
ASCII graph showing task dependencies. Include the critical path.

### Blocked Tasks Summary
Table: Task | Blocked By | Reason (specific, not generic)

### Effort Estimate
Total per phase and overall.

## Rules
- Every implementation task must have a paired test task
- P0 tasks must form a complete connected subgraph
- Specific file names in every task description (not "implement client")
- No circular dependencies
- Do NOT plan tasks for components not in the approved architecture
- Do NOT plan implementation of features deferred to v2 in design review

## Save & Archive
1. Write to `docs/${testCase}/impl-plan.md`
2. Copy to `outputs/${testCase}/phase-4-impl-planning/output.md`
3. Write `outputs/${testCase}/phase-4-impl-planning/agent-log.json`
4. Update `outputs/${testCase}/phase-status.json` → `phases."4".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 4: Implementation Planning ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Total tasks: [count] | P0 tasks: [count]          ║
║  • Critical path length: [estimate]                  ║
║  • Total effort estimate: [sum]                      ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 4 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 4 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
