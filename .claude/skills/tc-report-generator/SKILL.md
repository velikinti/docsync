# DocSync — TC Report Generator Skill

## Purpose
Generate a comprehensive HTML, Markdown, or JSON report of all DocSync SDLC test case pipeline runs.

## When to Use
- When the user says "generate report", "test case report", "pipeline status report", "show all TCs"
- After completing one or more test cases and wanting a summary
- For stakeholder reporting or audit

---

## Instructions

### Option A — CLI (PowerShell)

Run the report generator script:

```powershell
# HTML report (default)
scripts\generate-tc-report.ps1

# Markdown report
scripts\generate-tc-report.ps1 -Format markdown

# JSON report
scripts\generate-tc-report.ps1 -Format json

# Report for a single TC
scripts\generate-tc-report.ps1 -TestCase TC-003

# Custom output path
scripts\generate-tc-report.ps1 -Format html -OutputFile reports\my-report.html
```

Reports are saved to `reports/tc-report-<timestamp>.<ext>`.

### Option B — Agent-Generated (in-chat)

Read the following files to gather data:
1. `outputs/phase-status.json` — master list of all test cases
2. For each TC: `outputs/<TC>/phase-status.json` — phase details

#### Summary Table
| TC | User Story | Status | Phases Approved | Completed At |
|----|------------|--------|-----------------|--------------|
| TC-001 | US-001: … | COMPLETE | 8/8 | … |
| TC-002 | US-002: … | COMPLETE | 8/8 | … |

#### Per-TC Phase Detail (on request)
| Phase | Name | Status | Decided At |
|-------|------|--------|-----------|
| 1 | Requirements | ✅ APPROVED | … |
| 2 | Architecture | ✅ APPROVED | … |

#### HTML Report (on request)
Generate a self-contained HTML file with:
- Status badge colors: green=APPROVED, orange=PENDING, red=REJECTED, gray=NOT_STARTED
- Progress bars for each TC (phases_approved / 8)
- Summary cards at top (total, complete, in-progress, failed)
- No external CDN dependencies

#### JSON Report (on request)
```json
{
  "generated_at": "<ISO timestamp>",
  "project": "DocSync",
  "summary": { "total_tcs": N, "complete": N, "in_progress": N, "failed": N },
  "test_cases": [
    {
      "tc_id": "TC-001",
      "user_story": "US-001: ...",
      "pipeline_status": "PIPELINE_COMPLETE",
      "phases_approved": 8,
      "phases_total": 8,
      "pr_url": "...",
      "phases": [{ "phase": 1, "name": "Requirements", "status": "APPROVED", "decided_at": "..." }]
    }
  ]
}
```

---

## Report Sections (Full Report)
1. **Executive Summary** — total TCs, phases completed, in-progress, failed
2. **Test Case Table** — one row per TC with status, user story, dates
3. **Phase Detail** — per-TC breakdown of all 8 phases
4. **Findings** — any rejections noted in approval files

---

## Required Parameters

| Parameter | Required | Default |
|-----------|----------|---------|
| `Format` | No | `markdown` |
| `TestCase` | No | all TCs |
| `OutputFile` | No | `outputs/pipeline-report.<ext>` |
