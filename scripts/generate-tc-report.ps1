#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Generate Test Cases Reports for all DocSync SDLC pipeline runs.

.DESCRIPTION
    Reads outputs/phase-status.json and each TC-XXX/phase-status.json to produce
    HTML/Markdown/JSON reports. By default generates one combined report. Use
    -SeparateByTC to produce individual reports per user story under reports/TC-XXX/.
    Use -Evidence to embed the full verification output (test results, coverage,
    traceability matrix) as a test evidence section in each report.

.EXAMPLE
    # Combined summary report (default)
    scripts\generate-tc-report.ps1

    # Separate report per user story with test evidence
    scripts\generate-tc-report.ps1 -SeparateByTC -Evidence

    # Single TC with evidence, HTML
    scripts\generate-tc-report.ps1 -TestCase TC-002 -Evidence

    # All TCs separated, markdown format
    scripts\generate-tc-report.ps1 -SeparateByTC -Format markdown
#>

param(
    [ValidateSet("html", "markdown", "json")]
    [string]$Format = "html",
    [string]$OutputFile = "",
    [string]$TestCase = "",        # If set, report only this TC
    [switch]$SeparateByTC,         # Generate one report file per user story (TC)
    [switch]$Evidence              # Embed full verification output as test evidence
)

$Root        = Split-Path $PSScriptRoot -Parent
$OutputsDir  = Join-Path $Root "outputs"
$MasterFile  = Join-Path $OutputsDir "phase-status.json"
$ReportsDir  = Join-Path $Root "reports"
$Now         = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss UTC")

$PhaseNames = @{
    "1" = "Requirements"
    "2" = "Architecture"
    "3" = "Design Review"
    "4" = "Impl Planning"
    "5" = "Implementation"
    "6" = "Code Review"
    "7" = "Verification"
    "8" = "PR Creation"
}

# ── Load master status ─────────────────────────────────────────────────────────
if (-not (Test-Path $MasterFile)) {
    Write-Error "Master phase-status.json not found at $MasterFile"
    exit 1
}

$master = Get-Content $MasterFile -Raw | ConvertFrom-Json

# ── Collect TC data ────────────────────────────────────────────────────────────
$allTCs = @()
$tcKeys = if ($TestCase) { @($TestCase) } else { $master.test_cases.PSObject.Properties.Name }

foreach ($tcId in $tcKeys) {
    $tcStatusFile = Join-Path $OutputsDir "$tcId\phase-status.json"
    if (-not (Test-Path $tcStatusFile)) {
        Write-Warning "No phase-status.json found for $tcId — skipping"
        continue
    }
    $tc = Get-Content $tcStatusFile -Raw | ConvertFrom-Json

    $phases = @()
    for ($i = 1; $i -le 8; $i++) {
        $phaseKey = "$i"
        $phase    = $tc.phases.$phaseKey
        if ($phase) {
            $approvalFile = Join-Path $Root $phase.approval_file
            $approvedBy   = "—"
            if (Test-Path $approvalFile) {
                $ap = Get-Content $approvalFile -Raw | ConvertFrom-Json
                if ($ap.approved_by) { $approvedBy = $ap.approved_by }
            }
            $phases += [PSCustomObject]@{
                Number     = $i
                Name       = $phase.name
                Status     = $phase.status
                ApprovedAt = if ($phase.approved_at) { $phase.approved_at } else { "—" }
                ApprovedBy = $approvedBy
            }
        } else {
            $phases += [PSCustomObject]@{
                Number     = $i
                Name       = $PhaseNames[$phaseKey]
                Status     = "NOT_STARTED"
                ApprovedAt = "—"
                ApprovedBy = "—"
            }
        }
    }

    # Load test evidence from verification output if requested
    $evidenceText = ""
    if ($Evidence) {
        $verifyOutput = Join-Path $OutputsDir "$tcId\phase-7-verification\output.md"
        if (Test-Path $verifyOutput) {
            $evidenceText = Get-Content $verifyOutput -Raw -Encoding utf8
        }
    }

    $allTCs += [PSCustomObject]@{
        Id             = $tcId
        UserStory      = $tc.user_story
        PipelineStatus = if ($tc.pipeline_status) { $tc.pipeline_status } else { "IN_PROGRESS" }
        CurrentPhase   = $tc.current_phase
        InitializedAt  = $tc.initialized_at
        CompletedAt    = if ($tc.completed_at) { $tc.completed_at } else { "—" }
        Phases         = $phases
        Evidence       = $evidenceText
    }
}

# ── Helpers ────────────────────────────────────────────────────────────────────
function Status-Color($status) {
    switch ($status) {
        "APPROVED"         { return "#22c55e" }
        "COMPLETE"         { return "#22c55e" }
        "PENDING_APPROVAL" { return "#f59e0b" }
        "REJECTED"         { return "#ef4444" }
        "NOT_STARTED"      { return "#6b7280" }
        "IN_PROGRESS"      { return "#3b82f6" }
        default            { return "#9ca3af" }
    }
}

function Status-Badge-HTML($status) {
    $color = Status-Color $status
    return "<span style='background:$color;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.78em;font-weight:600'>$status</span>"
}

# ── Generate HTML (combined — all TCs) ────────────────────────────────────────
function Generate-HTML($tcs) {
    $totalTCs      = $tcs.Count
    $completedTCs  = ($tcs | Where-Object { $_.PipelineStatus -eq "COMPLETE" }).Count
    $inProgressTCs = ($tcs | Where-Object { $_.PipelineStatus -ne "COMPLETE" }).Count

    $tcRows = ""
    foreach ($tc in $tcs) {
        $tcRows += Build-TC-HTML-Block $tc $false
    }

    return @"
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DocSync — Test Cases Report</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
  h1 { color: #38bdf8; margin-bottom: 4px; }
  h2 { color: #38bdf8; }
  .meta { color: #64748b; font-size: 0.85em; margin-bottom: 24px; }
  .stats { display: flex; gap: 16px; margin-bottom: 28px; }
  .stat { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 24px; text-align: center; }
  .stat .num { font-size: 2em; font-weight: 700; color: #38bdf8; }
  .stat .lbl { font-size: 0.8em; color: #64748b; }
  pre { background:#0f172a;color:#a5f3fc;padding:14px;border-radius:6px;overflow-x:auto;font-size:0.82em;line-height:1.5;border:1px solid #1e3a5f; }
  code { font-family: 'Cascadia Code','Consolas',monospace; }
  table.ev { border-collapse:collapse;width:100%; }
  table.ev th { background:#0f172a;color:#64748b;padding:7px 10px;text-align:left;font-size:0.8em; }
  table.ev td { padding:6px 10px;border-bottom:1px solid #1e293b;font-size:0.85em; }
  .evidence-section { margin:16px 20px 20px; }
  details summary { cursor:pointer;color:#38bdf8;font-weight:600;padding:10px 0; }
</style>
</head>
<body>
<h1>DocSync — Test Cases Report</h1>
<div class="meta">Generated: $Now &nbsp;|&nbsp; Project: DocSync Agentic SDLC Pipeline</div>
<div class="stats">
  <div class="stat"><div class="num">$totalTCs</div><div class="lbl">Total Test Cases</div></div>
  <div class="stat"><div class="num" style="color:#22c55e">$completedTCs</div><div class="lbl">Completed</div></div>
  <div class="stat"><div class="num" style="color:#f59e0b">$inProgressTCs</div><div class="lbl">In Progress</div></div>
  <div class="stat"><div class="num">8</div><div class="lbl">SDLC Phases</div></div>
</div>
$tcRows
</body>
</html>
"@
}

# ── Generate HTML (single TC — standalone per-user-story report) ──────────────
function Generate-HTML-Single($tc) {
    $block = Build-TC-HTML-Block $tc $true
    return @"
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>DocSync — $($tc.Id) Report</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
  h1 { color: #38bdf8; margin-bottom: 4px; }
  h2 { color: #38bdf8; }
  .meta { color: #64748b; font-size: 0.85em; margin-bottom: 24px; }
  pre { background:#0f172a;color:#a5f3fc;padding:14px;border-radius:6px;overflow-x:auto;font-size:0.82em;line-height:1.5;border:1px solid #1e3a5f; }
  code { font-family: 'Cascadia Code','Consolas',monospace; }
  table.ev { border-collapse:collapse;width:100%; }
  table.ev th { background:#0f172a;color:#64748b;padding:7px 10px;text-align:left;font-size:0.8em; }
  table.ev td { padding:6px 10px;border-bottom:1px solid #1e293b;font-size:0.85em; }
  .evidence-section { margin:16px 20px 20px; }
  details summary { cursor:pointer;color:#38bdf8;font-weight:600;padding:10px 0; }
</style>
</head>
<body>
<h1>DocSync — $($tc.Id) Report</h1>
<div class="meta">Generated: $Now &nbsp;|&nbsp; User Story: $($tc.UserStory)</div>
$block
</body>
</html>
"@
}

# ── Build HTML block for a single TC (used by both combined and single reports) ─
function Build-TC-HTML-Block($tc, [bool]$expandEvidence) {
    $phaseHtml = ""
    foreach ($p in $tc.Phases) {
        $color = Status-Color $p.Status
        $phaseHtml += @"
            <tr>
                <td style='padding:4px 10px;color:#9ca3af'>Phase $($p.Number)</td>
                <td style='padding:4px 10px'>$($p.Name)</td>
                <td style='padding:4px 10px'><span style='background:$color;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:600'>$($p.Status)</span></td>
                <td style='padding:4px 10px;color:#9ca3af;font-size:0.85em'>$($p.ApprovedAt)</td>
            </tr>
"@
    }

    $badgeHtml = Status-Badge-HTML $tc.PipelineStatus

    # Build evidence section if available
    $evidenceHtml = ""
    if ($tc.Evidence) {
        $openAttr = if ($expandEvidence) { " open" } else { "" }
        # Convert the raw markdown evidence to a readable HTML block
        $escapedEvidence = $tc.Evidence `
            -replace '&','&amp;' `
            -replace '<','&lt;' `
            -replace '>','&gt;'

        # Extract key metrics via regex for a summary panel
        $passedMatch  = [regex]::Match($tc.Evidence, '(\d+)\s+passed')
        $coverMatch   = [regex]::Match($tc.Evidence, 'TOTAL\s+\d+\s+\d+\s+(\d+)%')
        $verdictMatch = [regex]::Match($tc.Evidence, '(?m)^\*\*(?:TC-\w+\s+)?Verdict:\s*(PASS|FAIL)\*\*')

        $passedCount  = if ($passedMatch.Success)  { $passedMatch.Groups[1].Value } else { "—" }
        $coverage     = if ($coverMatch.Success)   { "$($coverMatch.Groups[1].Value)%" } else { "—" }
        $verdict      = if ($verdictMatch.Success) { $verdictMatch.Groups[1].Value } else { "—" }
        $verdictColor = if ($verdict -eq "PASS")   { "#22c55e" } elseif ($verdict -eq "FAIL") { "#ef4444" } else { "#9ca3af" }

        $evidenceHtml = @"
        <div style='border-top:1px solid #334155;padding:14px 20px 0'>
            <div style='display:flex;gap:16px;margin-bottom:12px;flex-wrap:wrap'>
                <div style='background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 20px;text-align:center'>
                    <div style='font-size:1.5em;font-weight:700;color:#22c55e'>$passedCount</div>
                    <div style='font-size:0.75em;color:#64748b'>Tests Passed</div>
                </div>
                <div style='background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 20px;text-align:center'>
                    <div style='font-size:1.5em;font-weight:700;color:#38bdf8'>$coverage</div>
                    <div style='font-size:0.75em;color:#64748b'>Code Coverage</div>
                </div>
                <div style='background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 20px;text-align:center'>
                    <div style='font-size:1.5em;font-weight:700;color:$verdictColor'>$verdict</div>
                    <div style='font-size:0.75em;color:#64748b'>Verdict</div>
                </div>
            </div>
            <details$openAttr>
                <summary>Test Evidence — Full Verification Report</summary>
                <div class='evidence-section'>
                    <pre><code>$escapedEvidence</code></pre>
                </div>
            </details>
        </div>
"@
    }

    return @"
        <div style='background:#1e293b;border:1px solid #334155;border-radius:10px;margin-bottom:24px;overflow:hidden'>
            <div style='background:#0f172a;padding:16px 20px;border-bottom:1px solid #334155;display:flex;align-items:center;gap:16px'>
                <span style='font-size:1.2em;font-weight:700;color:#e2e8f0'>$($tc.Id)</span>
                $badgeHtml
                <span style='color:#94a3b8;font-size:0.85em;margin-left:auto'>Initialized: $($tc.InitializedAt)</span>
            </div>
            <div style='padding:14px 20px;border-bottom:1px solid #1e293b;color:#94a3b8;font-style:italic;font-size:0.93em'>
                $($tc.UserStory)
            </div>
            <div style='padding:10px 0'>
                <table style='width:100%;border-collapse:collapse'>
                    <thead>
                        <tr style='background:#0f172a'>
                            <th style='padding:8px 10px;text-align:left;color:#64748b;font-size:0.8em'>PHASE</th>
                            <th style='padding:8px 10px;text-align:left;color:#64748b;font-size:0.8em'>NAME</th>
                            <th style='padding:8px 10px;text-align:left;color:#64748b;font-size:0.8em'>STATUS</th>
                            <th style='padding:8px 10px;text-align:left;color:#64748b;font-size:0.8em'>APPROVED AT</th>
                        </tr>
                    </thead>
                    <tbody>$phaseHtml</tbody>
                </table>
            </div>
            $evidenceHtml
        </div>
"@
}


# ── Generate Markdown ──────────────────────────────────────────────────────────
function Generate-Markdown($tcs) {
    $lines = @()
    $lines += "# DocSync — Test Cases Report"
    $lines += ""
    $lines += "_Generated: $Now_"
    $lines += ""
    $lines += "## Summary"
    $lines += ""
    $lines += "| Metric | Count |"
    $lines += "|--------|-------|"
    $lines += "| Total Test Cases | $($tcs.Count) |"
    $lines += "| Completed | $(($tcs | Where-Object { $_.PipelineStatus -eq 'COMPLETE' }).Count) |"
    $lines += "| In Progress | $(($tcs | Where-Object { $_.PipelineStatus -ne 'COMPLETE' }).Count) |"
    $lines += ""

    foreach ($tc in $tcs) {
        $lines += "---"
        $lines += ""
        $lines += "## $($tc.Id) — ``$($tc.PipelineStatus)``"
        $lines += ""
        $lines += "> $($tc.UserStory)"
        $lines += ""
        $lines += "| Phase | Name | Status | Approved At |"
        $lines += "|-------|------|--------|-------------|"
        foreach ($p in $tc.Phases) {
            $lines += "| $($p.Number) | $($p.Name) | $($p.Status) | $($p.ApprovedAt) |"
        }
        $lines += ""
        if ($tc.Evidence) {
            $passedMatch = [regex]::Match($tc.Evidence, '(\d+)\s+passed')
            $coverMatch  = [regex]::Match($tc.Evidence, 'TOTAL\s+\d+\s+\d+\s+(\d+)%')
            $verdictMatch= [regex]::Match($tc.Evidence, '(?m)^\*\*(?:TC-\w+\s+)?Verdict:\s*(PASS|FAIL)\*\*')
            $lines += "### Test Evidence"
            $lines += ""
            $lines += "| Metric | Value |"
            $lines += "|--------|-------|"
            $lines += "| Tests Passed | $(if ($passedMatch.Success) { $passedMatch.Groups[1].Value } else { '—' }) |"
            $lines += "| Code Coverage | $(if ($coverMatch.Success) { "$($coverMatch.Groups[1].Value)%" } else { '—' }) |"
            $lines += "| Verdict | $(if ($verdictMatch.Success) { $verdictMatch.Groups[1].Value } else { '—' }) |"
            $lines += ""
            $lines += "<details><summary>Full Verification Report</summary>"
            $lines += ""
            $lines += '```'
            $lines += $tc.Evidence
            $lines += '```'
            $lines += ""
            $lines += "</details>"
            $lines += ""
        }
    }

    return $lines -join "`n"
}

# ── Generate Markdown (single TC) ─────────────────────────────────────────────
function Generate-Markdown-Single($tc) {
    $lines = @()
    $lines += "# DocSync — $($tc.Id) Report"
    $lines += ""
    $lines += "_Generated: $Now_"
    $lines += ""
    $lines += "> **User Story:** $($tc.UserStory)"
    $lines += ""
    $lines += "**Pipeline Status:** ``$($tc.PipelineStatus)``  "
    $lines += "**Initialized:** $($tc.InitializedAt)  "
    $lines += "**Completed:** $($tc.CompletedAt)"
    $lines += ""
    $lines += "## SDLC Phases"
    $lines += ""
    $lines += "| Phase | Name | Status | Approved At |"
    $lines += "|-------|------|--------|-------------|"
    foreach ($p in $tc.Phases) {
        $lines += "| $($p.Number) | $($p.Name) | $($p.Status) | $($p.ApprovedAt) |"
    }
    $lines += ""
    if ($tc.Evidence) {
        $passedMatch = [regex]::Match($tc.Evidence, '(\d+)\s+passed')
        $coverMatch  = [regex]::Match($tc.Evidence, 'TOTAL\s+\d+\s+\d+\s+(\d+)%')
        $verdictMatch= [regex]::Match($tc.Evidence, '(?m)^\*\*(?:TC-\w+\s+)?Verdict:\s*(PASS|FAIL)\*\*')
        $lines += "## Test Evidence"
        $lines += ""
        $lines += "| Metric | Value |"
        $lines += "|--------|-------|"
        $lines += "| Tests Passed | $(if ($passedMatch.Success) { $passedMatch.Groups[1].Value } else { '—' }) |"
        $lines += "| Code Coverage | $(if ($coverMatch.Success) { "$($coverMatch.Groups[1].Value)%" } else { '—' }) |"
        $lines += "| Verdict | $(if ($verdictMatch.Success) { $verdictMatch.Groups[1].Value } else { '—' }) |"
        $lines += ""
        $lines += "<details><summary>Full Verification Report</summary>"
        $lines += ""
        $lines += '```'
        $lines += $tc.Evidence
        $lines += '```'
        $lines += ""
        $lines += "</details>"
    }
    return $lines -join "`n"
}

# ── Generate JSON ──────────────────────────────────────────────────────────────
function Generate-JSON($tcs) {
    return $tcs | ConvertTo-Json -Depth 10
}

# ── Determine output path ──────────────────────────────────────────────────────
$stamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
if (-not (Test-Path $ReportsDir)) { New-Item -ItemType Directory -Path $ReportsDir -Force | Out-Null }

# ── Render and write ──────────────────────────────────────────────────────────
if ($SeparateByTC) {
    # One report per user story (TC)
    foreach ($tc in $allTCs) {
        $tcReportsDir = Join-Path $ReportsDir $tc.Id
        if (-not (Test-Path $tcReportsDir)) { New-Item -ItemType Directory -Path $tcReportsDir -Force | Out-Null }

        $ext = $Format
        $suffix = if ($Evidence) { "-with-evidence" } else { "" }
        $file = Join-Path $tcReportsDir "$($tc.Id)-report$suffix-$stamp.$ext"

        $content = switch ($Format) {
            "html"     { Generate-HTML-Single $tc }
            "markdown" { Generate-Markdown-Single $tc }
            "json"     { $tc | ConvertTo-Json -Depth 10 }
        }

        $content | Out-File -FilePath $file -Encoding utf8 -Force
        Write-Host "  $($tc.Id)  →  $file" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  Separate per-TC reports generated in: $ReportsDir\<TC-XXX>\" -ForegroundColor Cyan
    Write-Host "  Format   : $Format" -ForegroundColor White
    Write-Host "  Evidence : $($Evidence.IsPresent)" -ForegroundColor White
    Write-Host "  TCs      : $($allTCs.Count)" -ForegroundColor White
    Write-Host ""
} else {
    # Single combined report
    if (-not $OutputFile) {
        $ext = $Format
        $suffix = if ($Evidence) { "-with-evidence" } else { "" }
        $OutputFile = Join-Path $ReportsDir "tc-report$suffix-$stamp.$ext"
    }

    $content = switch ($Format) {
        "html"     { Generate-HTML $allTCs }
        "markdown" { Generate-Markdown $allTCs }
        "json"     { Generate-JSON $allTCs }
    }

    $content | Out-File -FilePath $OutputFile -Encoding utf8 -Force

    Write-Host ""
    Write-Host "  Test Cases Report Generated" -ForegroundColor Cyan
    Write-Host "  Format   : $Format" -ForegroundColor White
    Write-Host "  File     : $OutputFile" -ForegroundColor Green
    Write-Host "  Evidence : $($Evidence.IsPresent)" -ForegroundColor White
    Write-Host "  TCs      : $($allTCs.Count)" -ForegroundColor White
    Write-Host ""
}
