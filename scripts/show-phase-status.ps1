param(
    [Parameter(Mandatory=$false)]
    [string]$TestCase = ""
)

$Root = Split-Path $PSScriptRoot -Parent
$MasterStatusFile = Join-Path $Root "outputs\phase-status.json"

if (-not (Test-Path $MasterStatusFile)) {
    Write-Host ""
    Write-Host "  [DocSync Pipeline] No pipeline status found. Run the sdlc-orchestrator agent to start." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

try {
    $master = Get-Content $MasterStatusFile -Raw | ConvertFrom-Json
} catch {
    Write-Host "  [DocSync Pipeline] Could not read phase-status.json: $_" -ForegroundColor Red
    exit 0
}

# Determine which TC(s) to display
$tcsToShow = @()
if ($TestCase) {
    $tcsToShow = @($TestCase)
} elseif ($master.active_test_cases -and $master.active_test_cases.Count -gt 0) {
    $tcsToShow = $master.active_test_cases
} else {
    $tcsToShow = @("TC-001")
}

$StatusColors = @{
    "APPROVED"         = "Green"
    "COMPLETE"         = "Green"
    "IN_PROGRESS"      = "Cyan"
    "PENDING_APPROVAL" = "Yellow"
    "PENDING"          = "DarkGray"
    "REJECTED"         = "Red"
    "FAILED"           = "Red"
}
$StatusSymbols = @{
    "APPROVED"         = "[OK]"
    "COMPLETE"         = "[OK]"
    "IN_PROGRESS"      = "[..]"
    "PENDING_APPROVAL" = "[??]"
    "PENDING"          = "[  ]"
    "REJECTED"         = "[!!]"
    "FAILED"           = "[!!]"
}
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

foreach ($tcId in $tcsToShow) {
    $tcStatusFile = Join-Path $Root "outputs\$tcId\phase-status.json"

    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor DarkCyan
    Write-Host "    DocSync SDLC Pipeline  --  $tcId" -ForegroundColor Cyan
    Write-Host "  ============================================================" -ForegroundColor DarkCyan

    if (-not (Test-Path $tcStatusFile)) {
        Write-Host "  No phase-status.json found for $tcId." -ForegroundColor Yellow
        Write-Host "  Expected: outputs\$tcId\phase-status.json" -ForegroundColor DarkGray
        Write-Host "  ============================================================" -ForegroundColor DarkCyan
        Write-Host ""
        continue
    }

    try {
        $status = Get-Content $tcStatusFile -Raw | ConvertFrom-Json
    } catch {
        Write-Host "  Could not read phase-status.json: $_" -ForegroundColor Red
        continue
    }

    Write-Host ""
    Write-Host "    Phase  Name               Status              Output Path" -ForegroundColor DarkGray
    Write-Host "    -----  -----------------  ------------------  --------------------------------" -ForegroundColor DarkGray

    foreach ($i in 1..8) {
        $key        = "$i"
        $name       = $PhaseNames[$key]
        $folder     = $PhaseFolders[$key]
        $outputPath = "outputs\$tcId\$folder\output.md"

        if ($status.phases.PSObject.Properties[$key]) {
            $phase       = $status.phases.$key
            $phaseStatus = if ($phase.status) { $phase.status } else { "PENDING" }
        } else {
            $phaseStatus = "PENDING"
        }

        $symbol        = if ($StatusSymbols[$phaseStatus]) { $StatusSymbols[$phaseStatus] } else { "[?]" }
        $color         = if ($StatusColors[$phaseStatus])  { $StatusColors[$phaseStatus] }  else { "White" }
        $currentMarker = if ($status.current_phase -eq $i) { " << CURRENT" } else { "" }

        $namePad   = $name + (" " * (18 - $name.Length))
        $statusPad = $phaseStatus + (" " * (19 - $phaseStatus.Length))

        Write-Host -NoNewline "    $i      $symbol  $namePad"
        Write-Host -NoNewline $statusPad -ForegroundColor $color
        Write-Host -NoNewline $outputPath -ForegroundColor DarkGray
        if ($currentMarker) {
            Write-Host -NoNewline $currentMarker -ForegroundColor Yellow
        }
        Write-Host ""
    }

    Write-Host ""

    $pipelineStatus = if ($status.pipeline_status) { $status.pipeline_status } else { "IN_PROGRESS" }
    $pipelineColor  = if ($pipelineStatus -eq "COMPLETE") { "Green" } else { "Yellow" }

    Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host -NoNewline "    Pipeline: "
    Write-Host $pipelineStatus -ForegroundColor $pipelineColor
    Write-Host "    Outputs:  outputs\$tcId\phase-N-name\  (all 8 phases)" -ForegroundColor DarkGray

    $pendingPhases = @()
    foreach ($i in 1..8) {
        $key = "$i"
        if ($status.phases.PSObject.Properties[$key]) {
            if ($status.phases.$key.status -eq "PENDING_APPROVAL") {
                $pendingPhases += "Phase $i ($($PhaseNames[$key]))"
            }
        }
    }

    if ($pendingPhases.Count -gt 0) {
        $pendingList = $pendingPhases -join ", "
        Write-Host "    Awaiting: $pendingList" -ForegroundColor Yellow
        Write-Host "    Approve:  scripts\approve-phase.ps1 -Phase N -Decision APPROVED -TestCase $tcId" -ForegroundColor DarkGray
    } elseif ($pipelineStatus -eq "COMPLETE") {
        Write-Host "    All phases approved. Ready to create GitHub PR." -ForegroundColor DarkGray
    } else {
        $cur     = $status.current_phase
        $curName = $PhaseNames["$cur"]
        Write-Host "    Continue: Phase $cur ($curName) agent for $tcId" -ForegroundColor DarkGray
    }

    Write-Host "  ============================================================" -ForegroundColor DarkCyan
    Write-Host ""
}
