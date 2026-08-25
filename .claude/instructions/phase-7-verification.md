---
applyTo: "docs/TC-*/verification.md"
---

# Instructions — Phase 7: Verification

## Role
You are a QA engineer running verification. Your job is to execute tests and validate behavior — not to write new tests (that was Phase 5). Provide actual evidence, not descriptions of what tests would show.

## Verification is Evidence-Based
- Every claim must be backed by actual command output
- Copy terminal output verbatim — do not summarize or paraphrase
- If a test fails, reproduce the failure exactly
- Do NOT write "tests should pass" — run them and show the output

## Execution Steps (Run All)

### 1. Environment Verification
```bash
python --version    # Must be 3.10+
pip list | grep -E "httpx|pydantic|tenacity|structlog|click|markdown2|lxml"
```

### 2. Syntax Validation
```bash
python -m py_compile src/docsync/config.py
python -m py_compile src/docsync/github_client.py
python -m py_compile src/docsync/converter.py
python -m py_compile src/docsync/confluence_client.py
python -m py_compile src/docsync/sync.py
python -m py_compile src/docsync/main.py
```

### 3. Full Test Suite
```bash
pytest tests/ -v --tb=short
```
Capture COMPLETE output including the test session header and summary.

### 4. Coverage Report
```bash
pytest tests/ --cov=src/docsync --cov-report=term-missing
```
Include full per-file coverage table.

### 5. Dry-Run Test
```bash
docsync sync --dry-run --config .docsync.yml
```
or
```bash
python -m docsync.main sync --dry-run --config .docsync.yml
```
Must exit 0 (or show only "dry-run" messages if env vars not set).

### 6. Security Scan
```bash
grep -rn "password\|api_key\|token" src/docsync/*.py | grep -v "os.environ\|structlog\|sanitise\|redact\|token.*param\|token.*field\|token.*type" || echo "CLEAN"
```

### 7. Requirements Traceability
For each FR-01..FR-12, find the test that covers it:
```bash
grep -rn "FR-0" tests/
```

## Verification Report Format
Structure the report as:
1. Environment (versions)
2. Syntax validation results
3. Full test session output (verbatim copy)
4. Coverage table
5. Dry-run output
6. Security scan results
7. Requirements traceability matrix
8. Verdict: PASS / FAIL with specific reasons

## Pass/Fail Criteria
**PASS requires ALL:**
- `pytest tests/ -v` → 0 failures
- Overall coverage ≥ 70%
- Dry-run exits 0
- Security scan: CLEAN
- All SDLC phase docs exist in `docs/`

**FAIL if ANY:**
- Any test fails
- Coverage < 60% for any module (not just overall)
- Dry-run throws unhandled exception
- Hardcoded credentials found

## Prohibited Behaviors
- Do NOT fabricate test output — execute and copy
- Do NOT mark verification as PASS without running every step
- Do NOT skip the security scan
- Do NOT hide failing tests — report them and their tracebacks
