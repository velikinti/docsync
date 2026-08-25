---
description: "Phase 7 — Run verification suite and produce test evidence report. Usage: /verification TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# DocSync Phase 7 — Verification

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are a QA engineer for the DocSync project. Execute the full verification suite and produce a verification report. Provide actual evidence — not descriptions of what tests would show.

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"6"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 6 (Code Review) is not APPROVED.

## Execute and Capture Output (All Steps Required)

Run each command and copy the ACTUAL output verbatim — do NOT fabricate results.

### 1. Environment Verification
```powershell
python --version
pip list | Select-String "httpx|pydantic|tenacity|structlog|click|markdown2|lxml"
```

### 2. Syntax Validation
```powershell
python -m py_compile src/docsync/config.py
python -m py_compile src/docsync/github_client.py
python -m py_compile src/docsync/converter.py
python -m py_compile src/docsync/confluence_client.py
python -m py_compile src/docsync/sync.py
python -m py_compile src/docsync/main.py
```

### 3. Full Test Suite
```powershell
pytest tests/ -v --tb=short
```
Capture COMPLETE output including the session header and summary line.

### 4. Coverage Report
```powershell
pytest tests/ --cov=src/docsync --cov-report=term-missing
```
Include full per-file coverage table.

### 5. Dry-Run Test
```powershell
docsync sync --dry-run --config .docsync.yml
```
Must exit 0 (or show only "dry-run" messages if env vars not set).

### 6. Security Scan
```powershell
grep -rn "password|api_key|token" src/docsync/ | Where-Object { $_ -notmatch "os.environ|sanitise|redact" }
# Should be CLEAN
```

### 7. Requirements Traceability
For each FR in `docs/${testCase}/requirements.md`, identify the test function that covers it.
```powershell
grep -rn "def test_" tests/
```

## Pass Criteria
- All tests pass (0 failures)
- Coverage ≥ 70% overall
- Dry-run exits 0
- Security scan CLEAN
- All SDLC phase docs exist in `docs/${testCase}/`

## Output: `docs/${testCase}/verification.md`

Structure:
1. Environment (Python version, key package versions)
2. Syntax validation results
3. Full test session output (verbatim)
4. Coverage table (verbatim)
5. Dry-run output
6. Security scan results
7. Requirements traceability matrix (FR-XX → test function)
8. Verdict: **PASS** or **FAIL** (with specific reason if FAIL)

## Save & Archive
1. Write to `docs/${testCase}/verification.md`
2. Copy to `outputs/${testCase}/phase-7-verification/output.md`
3. Write `outputs/${testCase}/phase-7-verification/agent-log.json`
4. Update `outputs/${testCase}/phase-status.json` → `phases."7".status` = `"PENDING_APPROVAL"`.

## Human Checkpoint

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 7: Verification            ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • Test result: [X passed, Y failed]                 ║
║  • Coverage: [overall %]                             ║
║  • Dry-run: [PASS / FAIL]                            ║
║  • Security scan: [CLEAN / issues found]             ║
║  • Verdict: [PASS / FAIL]                            ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 7 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 7 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```
