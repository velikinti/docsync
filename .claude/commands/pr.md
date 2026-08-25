---
description: "Phase 8 — Create PR description, reviewer checklist, and CHANGELOG. Usage: /pr TC-XXX"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
---

# DocSync Phase 8 — PR Creation

## TC ID Resolution
$ARGUMENTS contains the test case ID (e.g. `TC-003`).
- If provided, use it as `${testCase}`.
- If not provided, read `outputs/phase-status.json` → `active_test_cases[0]`.

## Role
You are completing Phase 8 of the DocSync Agentic SDLC pipeline. Create the PR package — the final deliverable of the cycle.

## Pre-flight Check
Read `outputs/${testCase}/phase-status.json` and verify phase `"7"` has `"status": "APPROVED"`. If not:
> **Stop.** Phase 7 (Verification) is not APPROVED.

## Outputs Required

### 1. `docs/${testCase}/pr-description.md` (ALL 5 sections mandatory)

**Section 1 — Summary** (2–3 sentences):
What was built, why (the user story), and that it was driven by an 8-phase Agentic SDLC pipeline using Claude Code.

**Section 2 — Changes Made** (4 tables):
- SDLC Artifacts: `docs/${testCase}/*.md` files
- Source Code: `src/docsync/*.py` with specific reason per file
- Infrastructure: workflow, commands, agents, config files
- Tests: `tests/*.py` with what each covers

Every modified file must appear in exactly one table.

**Section 3 — Test Evidence**:
Copy the test session output from `docs/${testCase}/verification.md` VERBATIM.
Include the platform line, test collection count, and final summary. Include the coverage table.

**Section 4 — Known Limitations**:
Every PARTIAL finding from code-review.md and every DEFERRED item from design-review.md.
Format: what the limitation is, and why it was deferred.

**Section 5 — Reviewer Checklist** (actionable, independently verifiable):
```markdown
- [ ] FR-XX: Check `file.py` line N implements <specific behavior>
- [ ] NFR-01 (Security): No hardcoded secrets — verify with `grep -rn "token\s*=" src/`
- [ ] NFR-03 (Retry): tenacity decorator on `create_page`, `update_page`, `archive_page`
- [ ] NFR-07 (Idempotency): `find_page` in `confluence_client.py` uses `docsync:source_path`
- [ ] Run tests: `pytest tests/ -v --tb=short`
- [ ] Dry-run: `docsync sync --dry-run --config .docsync.yml`
- [ ] DD-01..DD-05: each design decision is implemented (list file/line for each)
```

### 2. CHANGELOG.md
Create/update with a version entry:
```markdown
## [X.X.X] - YYYY-MM-DD

### Added
- <List each major feature>

### Architecture
- <Key architectural decisions from design review>

### Known Limitations (vX)
- <List deferred items>
```

## Rules
- Test output must be actual output from `docs/${testCase}/verification.md` — not paraphrased
- Every file created must appear in the Changes Made section
- Known limitations must be honest and complete
- Reviewer checklist items must be independently verifiable

## Save & Archive
1. Write PR description to `docs/${testCase}/pr-description.md`
2. Copy to `outputs/${testCase}/phase-8-pr/output.md`
3. Write `outputs/${testCase}/phase-8-pr/agent-log.json`
4. Update `outputs/${testCase}/phase-status.json`:
   - `phases."8".status` = `"PENDING_APPROVAL"`
   - `pipeline_status` = `"PIPELINE_COMPLETE_PENDING_APPROVAL"`

## Human Checkpoint (Final Phase)

```
╔══════════════════════════════════════════════════════╗
║  HUMAN CHECKPOINT — Phase 8: PR Creation             ║
║  *** PIPELINE COMPLETE ***                           ║
╠══════════════════════════════════════════════════════╣
║  Test Case : ${testCase}                             ║
║  Status    : PENDING_APPROVAL                        ║
╠══════════════════════════════════════════════════════╣
║  • PR description: docs/${testCase}/pr-description.md║
║  • CHANGELOG.md: [updated / created]                 ║
║  • All 8 SDLC phases complete                        ║
╠══════════════════════════════════════════════════════╣
║  Approve:                                            ║
║    scripts\approve-phase.ps1 -Phase 8 -Decision APPROVED -TestCase ${testCase}
║  Reject:                                             ║
║    scripts\approve-phase.ps1 -Phase 8 -Decision REJECTED -Reason "..." -TestCase ${testCase}
╚══════════════════════════════════════════════════════╝
```

After Phase 8 is approved, use `docs/${testCase}/pr-description.md` as the GitHub PR body.
To publish to Confluence and create the PR automatically, use the agents:
- **Confluence**: Ask Claude to use the `confluence-publisher` agent for `${testCase}`
- **GitHub PR**: Ask Claude to use the `github-pr-creator` agent for `${testCase}`
