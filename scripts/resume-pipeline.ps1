#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Resume a DocSync SDLC pipeline from a specific phase, optionally stopping
    at a target phase (run only a subset of phases).

.DESCRIPTION
    Two modes:

      1. Resume after interruption     : -FromPhase 3
         Keeps phases 1-2 APPROVED; resets 3-8 to PENDING.

      2. Run only a range of phases    : -FromPhase 4 -ToPhase 6
         Bypasses phases before FromPhase (marks them BYPASSED if not yet
         APPROVED), resets phases 4-6 to PENDING, marks phases 7+ SKIPPED.

.EXAMPLE
    # Resume TC-003 from Phase 3 (keeps 1-2 APPROVED)
    scripts\resume-pipeline.ps1 -TestCase TC-003 -FromPhase 3

    # Run only phases 4, 5, 6
    scripts\resume-pipeline.ps1 -TestCase TC-003 -FromPhase 4 -ToPhase 6

    # Preview without writing
    scripts\resume-pipeline.ps1 -TestCase TC-003 -FromPhase 4 -ToPhase 6 -WhatIf

    # Skip confirmation prompt
    scripts\resume-pipeline.ps1 -TestCase TC-003 -FromPhase 4 -ToPhase 6 -Force
#>

param(
    [Parameter(Mandatory)]
    [string]$TestCase,

    [Parameter(Mandatory)]
    [ValidateRange(1, 8)]
    [int]$FromPhase,

    [ValidateRange(1, 8)]
    [int]$ToPhase = 8,

    [switch]$Force,
    [switch]$WhatIf
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($ToPhase -lt $FromPhase) {
    Write-Error "-ToPhase ($ToPhase) must be >= -FromPhase ($FromPhase)."
    exit 1
}

$Root         = Split-Path $PSScriptRoot -Parent
$TcStatusFile = Join-Path $Root "outputs\$TestCase\phase-status.json"

$PhaseDisplayNames = @{
    "1" = "Requirements"
    "2" = "Architecture"
    "3" = "Design Review"
    "4" = "Implementation Planning"
    "5" = "Implementation"
    "6" = "Code Review"
    "7" = "Verification"
    "8" = "PR Creation"
}

$PhaseFolders = @{
    "1" = "phase-1-requirements"
    "2" = "phase-2-architecture"
    "3" = "phase-3-design-review"
    "4" = "phase-4-impl-planning"
    "5" = "phase-5-implementation"
    "6" = "phase-6-code-review"
    "7" = "phase-7-verification"
    "8" = "phase-8-pr"
}

$PhasePrompts = @{
    "1" = "@requirements.prompt.md"
    "2" = "@architecture.prompt.md"
    "3" = "@design-review.prompt.md"
    "4" = "@impl-planning.prompt.md"
    "5" = "@implementation.prompt.md"
    "6" = "@code-review.prompt.md"
    "7" = "@verification.prompt.md"
    "8" = "@pr.prompt.md"
}

# ? Validate TC exists ?
if (-not (Test-Path $TcStatusFile)) {
    Write-Error "No pipeline found for $TestCase. Expected: $TcStatusFile"
    exit 1
}

$status = Get-Content $TcStatusFile -Raw | ConvertFrom-Json

$rangeMode  = ($ToPhase -lt 8)
$rangeLabel = if ($rangeMode) { "Phases $FromPhase-$ToPhase only" } else { "Phase $FromPhase onward" }

# ? Show plan ?
Write-Host ""
Write-Host "  DocSync Pipeline Resume" -ForegroundColor Cyan
Write-Host "  Test Case : $TestCase" -ForegroundColor White
Write-Host "  Run Range : $rangeLabel" -ForegroundColor White
Write-Host ""
Write-Host "  Planned actions:" -ForegroundColor DarkGray

for ($i = 1; $i -le 8; $i++) {
    $key      = "$i"
    $phaseObj = $status.phases.$key
    $name     = $PhaseDisplayNames[$key]
    $st       = "NOT_STARTED"
    if ($phaseObj) { $st = $phaseObj.status }

    if ($i -lt $FromPhase) {
        if ($st -eq "APPROVED") {
            $action = "[KEEP]    APPROVED"
            $color  = "Green"
        } else {
            $action = "[BYPASS]  not yet approved"
            $color  = "DarkYellow"
        }
    } elseif ($i -ge $FromPhase -and $i -le $ToPhase) {
        $action = "[RUN]     will execute"
        $color  = "Yellow"
    } else {
        $action = "[SKIP]    excluded from range"
        $color  = "DarkGray"
    }

    Write-Host ("  Phase " + $i + " (" + $name + ")  ->  " + $action) -ForegroundColor $color
}

Write-Host ""

if ($WhatIf) {
    Write-Host "  [WhatIf] No changes written. Remove -WhatIf to apply." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  After applying, run in Copilot Chat:" -ForegroundColor DarkGray
    for ($i = $FromPhase; $i -le $ToPhase; $i++) {
        $p = $PhasePrompts["$i"]
        $n = $PhaseDisplayNames["$i"]
        Write-Host ("    Phase " + $i + " (" + $n + "):  Use $TestCase. $p") -ForegroundColor White
    }
    Write-Host ""
    exit 0
}

if (-not $Force) {
    $confirm = Read-Host "  Apply this plan? [y/N]"
    if ($confirm -notmatch "^[Yy]") {
        Write-Host "  Cancelled. Use -Force to skip." -ForegroundColor Yellow
        exit 0
    }
}

# ? Write changes ?
$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

for ($i = 1; $i -le 8; $i++) {
    $key    = "$i"
    $folder = $PhaseFolders[$key]
    $name   = $PhaseDisplayNames[$key]

    $phaseObj  = $status.phases.$key
    $currentSt = "NOT_STARTED"
    if ($phaseObj) { $currentSt = $phaseObj.status }

    if ($i -lt $FromPhase) {
        if ($currentSt -ne "APPROVED") {
            $entry = [ordered]@{
                name           = $name
                phase_folder   = $folder
                status         = "BYPASSED"
                output_archive = "outputs/$TestCase/$folder/output.md"
                approval_file  = "outputs/$TestCase/$folder/approval.json"
                bypassed_at    = $now
                bypassed_by    = "resume-pipeline (range=$FromPhase-$ToPhase)"
            }
            $status.phases.$key = $entry
        }
    } elseif ($i -ge $FromPhase -and $i -le $ToPhase) {
        $newSt = if ($currentSt -eq "APPROVED") { "RESET" } else { "PENDING" }
        $entry = [ordered]@{
            name           = $name
            phase_folder   = $folder
            status         = $newSt
            output_archive = "outputs/$TestCase/$folder/output.md"
            approval_file  = "outputs/$TestCase/$folder/approval.json"
            reset_at       = $now
            reset_from     = "resume-pipeline (range=$FromPhase-$ToPhase)"
        }
        $status.phases.$key = $entry
    } else {
        $entry = [ordered]@{
            name           = $name
            phase_folder   = $folder
            status         = "SKIPPED"
            output_archive = "outputs/$TestCase/$folder/output.md"
            approval_file  = "outputs/$TestCase/$folder/approval.json"
            skipped_at     = $now
            skipped_by     = "resume-pipeline (range=$FromPhase-$ToPhase)"
        }
        $status.phases.$key = $entry
    }
}

$status | Add-Member -MemberType NoteProperty -Name "current_phase"      -Value $FromPhase -Force
$status | Add-Member -MemberType NoteProperty -Name "pipeline_status"    -Value "IN_PROGRESS" -Force
$status | Add-Member -MemberType NoteProperty -Name "last_resumed_at"    -Value $now -Force
$status | Add-Member -MemberType NoteProperty -Name "resumed_from_phase" -Value $FromPhase -Force
$status | Add-Member -MemberType NoteProperty -Name "resumed_to_phase"   -Value $ToPhase -Force

$status | ConvertTo-Json -Depth 10 | Out-File -FilePath $TcStatusFile -Encoding utf8 -Force

# ? Summary ?
Write-Host "  Applied for $TestCase" -ForegroundColor Green
Write-Host ""
if ($rangeMode) {
    if ($FromPhase -gt 1) {
        Write-Host ("  Phases 1-" + ($FromPhase - 1) + "    : KEPT/BYPASSED (not re-run)") -ForegroundColor DarkGray
    }
    Write-Host ("  Phases $FromPhase-$ToPhase        : PENDING (will execute)") -ForegroundColor Yellow
    if ($ToPhase -lt 8) {
        Write-Host ("  Phases " + ($ToPhase + 1) + "-8     : SKIPPED") -ForegroundColor DarkGray
    }
} else {
    if ($FromPhase -gt 1) {
        Write-Host ("  Phases 1-" + ($FromPhase - 1) + " : APPROVED (unchanged)") -ForegroundColor Green
    }
    Write-Host ("  Phases $FromPhase-8 : reset to PENDING") -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Run these phases in Copilot Chat (in order):" -ForegroundColor Cyan
for ($i = $FromPhase; $i -le $ToPhase; $i++) {
    $p = $PhasePrompts["$i"]
    $n = $PhaseDisplayNames["$i"]
    Write-Host ("    Phase " + $i + " (" + $n + ")  ->  Use $TestCase. $p") -ForegroundColor White
}
Write-Host ""