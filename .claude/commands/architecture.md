---
description: "Phase 2 — Design system architecture based on approved requirements. Usage: /architecture TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
---

# DocSync Phase 2 — Architecture

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are a senior software architect for the DocSync project. Design a production-ready system architecture that satisfies all approved requirements.

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"1"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 1 (Requirements) is not APPROVED. Run:
> ```powershell
> scripts\approve-phase.ps1 -Phase 1 -Decision APPROVED -TestCase ${testCase}
> ```

## Architecture Document Sections (All Required)

Read `docs/${testCase}/requirements.md` first. Then produce `docs/${testCase}/architecture.md` with:

1. **System Overview**
   - 2–3 paragraph narrative
   - ASCII component diagram showing all components, data flows, and external systems

2. **Technology Choices**
   Table: Concern | Choice | Rationale
   Cover: language, HTTP client, config parsing, retry, CLI, testing, CI/CD, logging

3. **Component Responsibilities**
   For each component: file path, purpose, public method signatures, dependencies

4. **Data Flow**
   Numbered step-by-step from "GitHub push" to "Confluence page updated"

5. **Directory Layout**
   Complete file tree for the implementation

6. **Security Architecture**
   How secrets are handled, what is logged, what is safe to commit

7. **Error Handling Strategy**
   Table: Scenario | Behaviour for every failure mode

## Component Design Rules
- Each component has ONE responsibility (single responsibility principle)
- All external API calls in dedicated client modules
- All external calls are mockable (no direct HTTP in business logic)
- Configuration validated at startup via pydantic (fail fast)
- Retry logic is declarative (tenacity), not manual loops

## Traceability
After completing, verify every FR and NFR maps to a component or mechanism. Document any gaps.

## Save & Archive
1. Write to `docs/${testCase}/architecture.md`
2. Copy to `outputs/${testCase}/phase-2-architecture/output.md`
3. Write `outputs/${testCase}/phase-2-architecture/agent-log.json`:
   ```json
   {
     "phase": 2,
     "phase_name": "Architecture",
     "agent": "architecture.md (Claude Code slash command)",
     "completed_at": "<ISO timestamp>",
     "output_file": "docs/${testCase}/architecture.md",
     "output_archived_to": "outputs/${testCase}/phase-2-architecture/output.md",
     "status": "SUCCESS"
   }
   ```
4. Update `outputs/${testCase}/phase-status.json` → `phases."2".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 2: Architecture            ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Output: docs/${testCase}/architecture.md          ║
║  • Components defined: [count]                       ║
║  • Tech choices: [count]                             ║
║  • Error scenarios covered: [count]                  ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 2 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 2 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
