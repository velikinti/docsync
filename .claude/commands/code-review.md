---
description: "Phase 6 — Structured code review covering correctness, security, tests, and DRY. Usage: /code-review TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# DocSync Phase 6 — Code Review

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are a senior peer reviewer for the DocSync project. Read the actual implementation code. Find real bugs, not hypothetical ones. Be specific — "line 42 in sync.py" not "error handling could be improved."

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"5"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 5 (Implementation) is not APPROVED.

## Review Methodology
1. Read EVERY file in `src/docsync/` and `tests/`
2. Cross-reference against `docs/${testCase}/requirements.md` (FR traceability)
3. Verify design decisions DD-XX are implemented correctly
4. Check every test for correctness, not just existence

## Review Areas (All 7 Required)

### 1. Correctness (Requirement Traceability)
For every FR in `docs/${testCase}/requirements.md`:
- Find the specific code that implements it
- Verify the implementation matches the requirement
- Status: PASS / FAIL / PARTIAL

### 2. Security
```bash
grep -rn "token\s*=" src/ tests/   # check for hardcoded tokens
```
- Verify `os.environ` pattern in config.py
- Check structlog doesn't dump config objects (which contain tokens)
- Verify HTTP exception sanitisation in both clients
- Check `.docsync.yml` has no secrets

### 3. Error Handling
Test every error path:
- Tenacity retry: verify decorator is on mutating operations
- 404 handling: verify FileNotFoundError maps correctly
- Per-file exception isolation: verify one file failure doesn't abort the batch

### 4. Test Coverage
```powershell
pytest --cov=src/docsync --cov-report=term-missing
```
Flag any module < 80%. Check that tests assert correct behavior (not just "no exception").

### 5. Code Clarity
Read as a new team member. Flag anything confusing. Verify single responsibility per module.

### 6. DRY Principle
Look for the same code pattern appearing 3+ times. Check if the tenacity decorator is refactored.

### 7. Dependency Safety
Check `requirements.txt` for version ranges. Flag `>=X` without upper bound.

## Finding Format
```
**Finding CR-XX (SEVERITY):** `file.py`, line N. What is wrong.
**Recommendation:** Specific fix.
```

Severity: BLOCKER / HIGH / MEDIUM / LOW

Final verdict: PASS / PASS WITH MINOR ISSUES / FAIL (do NOT approve with BLOCKER findings)

## Output: `docs/${testCase}/code-review.md`

## Save & Archive
1. Write to `docs/${testCase}/code-review.md`
2. Copy to `outputs/${testCase}/phase-6-code-review/output.md`
3. Write `outputs/${testCase}/phase-6-code-review/agent-log.json`
4. Update `outputs/${testCase}/phase-status.json` → `phases."6".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 6: Code Review             ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Findings: [count BLOCKER/HIGH/MEDIUM/LOW]         ║
║  • Coverage: [overall %]                             ║
║  • Modules below 80%: [list or NONE]                 ║
║  • Final verdict: [PASS / PASS WITH MINOR / FAIL]    ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 6 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 6 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
