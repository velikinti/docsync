param(
    [ValidateRange(1, 8)][int]$Phase = 0,
    [ValidateRange(1, 8)][int]$Prereq = 0,
    [string]$TestCase = "TC-001"
)

$Root = Split-Path $PSScriptRoot -Parent
$tcId         = $TestCase
$tcStatusFile = Join-Path $Root "outputs\$tcId\phase-status.json"

$PhaseDisplayNames = @{
    1 = "Requirements"
    2 = "Architecture"
    3 = "Design Review"
    4 = "Implementation Planning"
    5 = "Implementation"
    6 = "Code Review"
    7 = "Verification"
    8 = "PR Creation"
}

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

if (-not (Test-Path $tcStatusFile)) {
    Write-Host "  [Status Check] No phase-status.json found for $tcId. Pipeline not yet initialized." -ForegroundColor Yellow
    Write-Host "  Expected: outputs\$tcId\phase-status.json" -ForegroundColor DarkGray
    exit 0
}

$status = Get-Content $tcStatusFile -Raw | ConvertFrom-Json

# Gate check: is Phase $Prereq APPROVED before proceeding to the next?
if ($Prereq -gt 0) {
    $prereqKey    = "$Prereq"
    $prereqObj    = $status.phases.$prereqKey
    $prereqStatus = if ($prereqObj) { $prereqObj.status } else { "NOT STARTED" }
    $prereqName   = $PhaseDisplayNames[$Prereq]

    if ($prereqStatus -ne "APPROVED") {
        $nextPhase = $Prereq + 1
        Write-Host ""
        Write-Host "  [BLOCKED] $tcId Phase $Prereq ($prereqName) is $prereqStatus" -ForegroundColor Red
        $msg = "  Phase " + $nextPhase + " cannot start until Phase " + $Prereq + " is APPROVED."
        Write-Host $msg -ForegroundColor Yellow
        Write-Host "  Run: scripts\approve-phase.ps1 -Phase $Prereq -Decision APPROVED -TestCase $tcId" -ForegroundColor DarkGray
        Write-Host ""
        exit 1
    }

    $nextPhase = $Prereq + 1
    Write-Host "  [OK] Gate cleared: $tcId Phase $Prereq ($prereqName) is APPROVED -- Phase $nextPhase may proceed." -ForegroundColor Green
    exit 0
}

# Single phase status check
if ($Phase -gt 0) {
    $phaseKey  = "$Phase"
    $phaseObj  = $status.phases.$phaseKey
    $phaseName = $PhaseDisplayNames[$Phase]
    $folder    = $PhaseFolders[$Phase]

    if (-not $phaseObj) {
        Write-Host "  $tcId Phase $Phase ($phaseName): NOT STARTED" -ForegroundColor DarkGray
        exit 0
    }

    $phaseStatus = $phaseObj.status
    $color = "White"
    if ($phaseStatus -eq "APPROVED")             { $color = "Green" }
    elseif ($phaseStatus -eq "IN_PROGRESS")      { $color = "Cyan" }
    elseif ($phaseStatus -eq "PENDING_APPROVAL") { $color = "Yellow" }
    elseif ($phaseStatus -in @("REJECTED","FAILED")) { $color = "Red" }

    Write-Host ""
    Write-Host "  $tcId  Phase $Phase ($phaseName)" -ForegroundColor White
    Write-Host -NoNewline "  Status: "
    Write-Host $phaseStatus -ForegroundColor $color
    Write-Host "  Output: outputs\$tcId\$folder\output.md" -ForegroundColor DarkGray

    if ($phaseObj.PSObject.Properties["completed_at"]) {
        Write-Host "  Completed: $($phaseObj.completed_at)"
    }
    if ($phaseObj.PSObject.Properties["approved_at"]) {
        Write-Host "  Approved:  $($phaseObj.approved_at)"
    }
    if ($phaseObj.PSObject.Properties["rejection_reason"]) {
        Write-Host "  Rejection: $($phaseObj.rejection_reason)" -ForegroundColor Yellow
    }

    $approvalFile = Join-Path $Root "outputs\$tcId\$folder\approval.json"
    if (Test-Path $approvalFile) {
        Write-Host "  Approval record: outputs\$tcId\$folder\approval.json" -ForegroundColor DarkGray
    }
    Write-Host ""
    exit 0
}

# Default: show summary of all phases for this TC
$completed = 0
$blocked   = 0
foreach ($i in 1..8) {
    $key = "$i"
    if ($status.phases.PSObject.Properties[$key]) {
        $s = $status.phases.$key.status
        if ($s -eq "APPROVED") { $completed++ }
        if ($s -in @("REJECTED", "FAILED")) { $blocked++ }
    }
}

$currentPhase = $status.current_phase
$currentName  = $PhaseDisplayNames[$currentPhase]

Write-Host ""
Write-Host "  $tcId  --  $completed/8 phases approved" -ForegroundColor Cyan
Write-Host "  Current phase: $currentPhase ($currentName)" -ForegroundColor White
Write-Host "  All outputs: outputs\$tcId\phase-N-name\" -ForegroundColor DarkGray

if ($blocked -gt 0) {
    Write-Host "  WARNING: $blocked phase(s) REJECTED or FAILED -- review needed" -ForegroundColor Red
}

$pendingApproval = @()
foreach ($i in 1..8) {
    $key = "$i"
    if ($status.phases.PSObject.Properties[$key]) {
        if ($status.phases.$key.status -eq "PENDING_APPROVAL") {
            $pendingApproval += "Phase $i"
        }
    }
}
if ($pendingApproval.Count -gt 0) {
    $pendingList = $pendingApproval -join ", "
    Write-Host "  Awaiting human approval: $pendingList" -ForegroundColor Yellow
}

Write-Host ""
exit 0
