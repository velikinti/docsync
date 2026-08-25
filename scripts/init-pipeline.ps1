#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Initialize or reset the DocSync SDLC pipeline for a test case (requirement).
    Creates the TC-XXX/ directory with all 8 phase subfolders and a fresh phase-status.json.

.DESCRIPTION
    Each TC-XXX represents one requirement/user story. All 8 SDLC phase outputs
    are stored under outputs/TC-XXX/phase-N-name/.

.EXAMPLE
    scripts\init-pipeline.ps1                          # Initialize TC-001 (default)
    scripts\init-pipeline.ps1 -TestCase TC-002         # Initialize TC-002 for a second requirement
    scripts\init-pipeline.ps1 -Force                   # Reset without confirmation
    scripts\init-pipeline.ps1 -FromPhase 4             # Restart from phase 4, keep 1-3 APPROVED
    scripts\init-pipeline.ps1 -TestCase TC-001 -Force  # Force-reset TC-001
#>

param(
    [switch]$Force,
    [ValidateRange(1, 8)]
    [int]$FromPhase = 1,
    [string]$TestCase = "TC-001",
    [string]$UserStory = ""
)

$Root         = Split-Path $PSScriptRoot -Parent
$OutputsDir   = Join-Path $Root "outputs"
$TcDir        = Join-Path $OutputsDir $TestCase
$TcStatusFile = Join-Path $TcDir "phase-status.json"
$MasterFile   = Join-Path $OutputsDir "phase-status.json"

Write-Host ""
Write-Host "  DocSync SDLC Pipeline Initializer" -ForegroundColor Cyan
Write-Host "  Test Case: $TestCase" -ForegroundColor White
Write-Host ""

# Check if this TC already exists
if (Test-Path $TcStatusFile) {
    $existing       = Get-Content $TcStatusFile -Raw | ConvertFrom-Json
    $existingStatus = if ($existing.pipeline_status) { $existing.pipeline_status } else { "IN_PROGRESS" }

    Write-Host "  Existing pipeline found for $TestCase : $existingStatus" -ForegroundColor Yellow

    if (-not $Force) {
        $confirm = Read-Host "  Reset $TestCase? This will overwrite its phase-status.json. [y/N]"
        if ($confirm -notmatch "^[Yy]") {
            Write-Host "  Cancelled. Use -Force to skip this prompt." -ForegroundColor Yellow
            exit 0
        }
    }
}

# Phase folder names
$PhaseFolders = @{
    1 = "phase-1-requirements"
    2 = "phase-2-architecture"
    3 = "phase-3-design-review"
    4 = "phase-4-impl-planning"
    5 = "phase-5-implementation"
    6 = "phase-6-code-review"
    7 = "phase-7-verification"
    8 = "phase-8-pr"
}

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

# Create TC directory and all 8 phase subdirectories
if (-not (Test-Path $TcDir)) {
    New-Item -ItemType Directory -Path $TcDir -Force | Out-Null
}

foreach ($num in 1..8) {
    $phaseDir = Join-Path $TcDir $PhaseFolders[$num]
    if (-not (Test-Path $phaseDir)) {
        New-Item -ItemType Directory -Path $phaseDir -Force | Out-Null
        Write-Host "  Created: outputs\$TestCase\$($PhaseFolders[$num])" -ForegroundColor DarkGray
    }
}

# Build per-TC phase-status.json
$phases = [ordered]@{}
foreach ($i in 1..8) {
    $key    = "$i"
    $folder = $PhaseFolders[$i]
    if ($i -lt $FromPhase) {
        $phases[$key] = @{
            name         = $PhaseDisplayNames[$key]
            phase_folder = $folder
            status       = "APPROVED"
            output_archive = "outputs/$TestCase/$folder/output.md"
            approval_file  = "outputs/$TestCase/$folder/approval.json"
            note         = "Pre-approved (pipeline started from Phase $FromPhase)"
        }
    } else {
        $phases[$key] = @{
            name           = $PhaseDisplayNames[$key]
            phase_folder   = $folder
            status         = "PENDING"
            output_archive = "outputs/$TestCase/$folder/output.md"
            approval_file  = "outputs/$TestCase/$folder/approval.json"
        }
    }
}

$now        = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$storyValue = if ($UserStory) { $UserStory } else { "See docs/requirements.md" }

$statusObj = [ordered]@{
    test_case_id     = $TestCase
    user_story       = $storyValue
    pipeline_status  = "IN_PROGRESS"
    initialized_at   = $now
    current_phase    = $FromPhase
    phases           = $phases
}

$statusObj | ConvertTo-Json -Depth 10 | Out-File -FilePath $TcStatusFile -Encoding utf8

# Update master phase-status.json
if (Test-Path $MasterFile) {
    try {
        $master = Get-Content $MasterFile -Raw | ConvertFrom-Json
        if (-not $master.test_cases.PSObject.Properties[$TestCase]) {
            $master.test_cases | Add-Member -MemberType NoteProperty -Name $TestCase -Value @{
                user_story       = $storyValue
                pipeline_status  = "IN_PROGRESS"
                status_file      = "outputs/$TestCase/phase-status.json"
                started_at       = $now
            } -Force
        } else {
            $master.test_cases.$TestCase.pipeline_status = "IN_PROGRESS"
            $master.test_cases.$TestCase | Add-Member -MemberType NoteProperty -Name "started_at" -Value $now -Force
        }
        # Add to active_test_cases if not already present
        $activeTcs = @($master.active_test_cases)
        if ($TestCase -notin $activeTcs) {
            $activeTcs += $TestCase
            $master | Add-Member -MemberType NoteProperty -Name "active_test_cases" -Value $activeTcs -Force
        }
        $master | Add-Member -MemberType NoteProperty -Name "last_updated" -Value $now -Force
        $master | ConvertTo-Json -Depth 10 | Out-File -FilePath $MasterFile -Encoding utf8
    } catch {
        Write-Host "  Warning: Could not update master status: $_" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "  [OK] $TestCase initialized. Starting from Phase $FromPhase." -ForegroundColor Green
Write-Host "  Status:  outputs\$TestCase\phase-status.json" -ForegroundColor DarkGray
Write-Host "  Outputs: outputs\$TestCase\phase-N-name\  (created for phases 1-8)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Spawn the sdlc-orchestrator agent: Agent(sdlc-orchestrator)" -ForegroundColor DarkGray
$phaseAgentNames = @{1="requirements";2="architecture";3="design-review";4="impl-planning";5="implementation";6="code-review";7="verification";8="pr"}
Write-Host "  2. Or run Phase $FromPhase only: Agent(sdlc-$($phaseAgentNames[$FromPhase]))" -ForegroundColor DarkGray
Write-Host "  3. Approve each phase: scripts\approve-phase.ps1 -Phase N -Decision APPROVED -TestCase $TestCase" -ForegroundColor DarkGray
Write-Host ""

& (Join-Path $PSScriptRoot "show-phase-status.ps1") -TestCase $TestCase
