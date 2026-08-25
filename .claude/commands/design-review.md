---
description: "Phase 3 — Conduct structured design review of architecture. Usage: /design-review TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
---

# DocSync Phase 3 — Design Review

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are a senior technical reviewer — skeptical, thorough, experience-driven. Your job is to find problems BEFORE code is written. Be critical.

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"2"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 2 (Architecture) is not APPROVED.

## Reviewer Mindset
- Assume the architecture has problems — find them
- Think like an attacker for security (what gets logged? what's in error messages?)
- Think about production incidents (what breaks at 3am?)
- Verify decisions against requirements

## Review Dimensions

### Risk Analysis
For each risk found:
- Risk ID (RISK-XX), Severity (HIGH/MEDIUM/LOW)
- What could go wrong and under what condition
- Agreed mitigation/design change
- Specific action required (or DEFERRED with reason)

Focus areas:
- **Idempotency**: Can the same operation run safely twice?
- **API rate limits**: Bulk operations may throttle
- **Data format conversion**: Edge cases in Markdown→Confluence XHTML
- **Secret exposure**: Could any failure mode leak credentials to logs?
- **Partial failure**: What if the batch fails halfway through?
- **Race conditions**: Async operations and concurrent writes

Severity criteria:
- **HIGH**: Data loss, security breach, or complete outage
- **MEDIUM**: Degraded functionality, wrong output, or performance issue
- **LOW**: Minor issue, edge case, code quality concern

### Gap Analysis
For each underspecified area:
- Gap ID (GAP-XX)
- What is missing from the architecture
- Resolution: which phase addresses it

### Design Decisions
Table: DD-XX | Decision | Rationale

### Architecture Updates
List exact changes needed in `architecture.md` — then make those changes directly.

## Output: `docs/${testCase}/design-review.md`

Final section: **Review Verdict** table covering functional completeness, security, performance, reliability, idempotency, testability.

Do NOT approve with unresolved HIGH risks.

## Save & Archive
1. Write to `docs/${testCase}/design-review.md`
2. Copy to `outputs/${testCase}/phase-3-design-review/output.md`
3. Write `outputs/${testCase}/phase-3-design-review/agent-log.json`
4. Update `outputs/${testCase}/phase-status.json` → `phases."3".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 3: Design Review           ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Risks found: [count HIGH/MEDIUM/LOW]              ║
║  • Gaps found: [count]                               ║
║  • Design decisions: [count DD-XX]                   ║
║  • Architecture updates applied: [YES/NO]            ║
║  • Review verdict: [PASS / FAIL]                     ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 3 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 3 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
