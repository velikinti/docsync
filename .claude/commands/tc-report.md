---
description: "Generate a status report for all DocSync SDLC test case pipeline runs. Usage: /tc-report [TC-XXX] [html|markdown|json]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
---

# DocSync — TC Status Report

## Inputs
$ARGUMENTS (optional): `[TC-XXX] [html|markdown|json]`

- No args → report all TCs, markdown format
- `TC-003` → report for TC-003 only
- `html` → HTML format
- `json` → JSON format

## What This Does

### Option A — Run PowerShell Report Script
```powershell
# All TCs, HTML
scripts\generate-tc-report.ps1

# Single TC
scripts\generate-tc-report.ps1 -TestCase TC-003

# Markdown format
scripts\generate-tc-report.ps1 -Format markdown

# JSON format
scripts\generate-tc-report.ps1 -Format json
```

### Option B — Agent-Generated In-Chat

1. Read `outputs/phase-status.json` — master list of all test cases
2. For each TC, read `outputs/<TC>/phase-status.json`
3. Produce a summary table:

| TC | User Story | Pipeline Status | Phases Approved | Completed At |
|----|------------|----------------|-----------------|--------------|
| TC-001 | US-001: ... | COMPLETE | 8/8 | ... |
| TC-002 | US-002: ... | COMPLETE | 8/8 | ... |

4. Show per-TC phase breakdown:

**TC-001 Phase Detail:**
| Phase | Name | Status | Decided At |
|-------|------|--------|-----------|
| 1 | Requirements | APPROVED | ... |
| 2 | Architecture | APPROVED | ... |
| ... | ... | ... | ... |

## Report Sections (Full Report)
1. **Executive Summary** — total TCs, phases completed, in-progress, failed
2. **Test Case Table** — one row per TC with status, user story, dates
3. **Phase Detail** — per-TC breakdown of all 8 phases
4. **Findings** — any rejections noted in approval files
