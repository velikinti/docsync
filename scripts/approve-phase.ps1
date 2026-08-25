param(
    [Parameter(Mandatory=$true)]
    [ValidateRange(1, 8)]
    [int]$Phase,

    [Parameter(Mandatory=$true)]
    [ValidateSet("APPROVED", "REJECTED")]
    [string]$Decision,

    [Parameter(Mandatory=$false)]
    [string]$Reason = "",

    [Parameter(Mandatory=$false)]
    [string]$TestCase = "TC-001"
)

$Root = Split-Path $PSScriptRoot -Parent
$MasterStatusFile = Join-Path $Root "outputs\phase-status.json"

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
    1 = "Requirements"
    2 = "Architecture"
    3 = "Design Review"
    4 = "Implementation Planning"
    5 = "Implementation"
    6 = "Code Review"
    7 = "Verification"
    8 = "PR Creation"
}

$tcId      = $TestCase
$phaseName = $PhaseFolders[$Phase]
$display   = $PhaseDisplayNames[$Phase]

# Path: outputs/TC-XXX/phase-N-name/
$phaseDir = Join-Path $Root "outputs\$tcId\$phaseName"
if (-not (Test-Path $phaseDir)) {
    New-Item -ItemType Directory -Path $phaseDir -Force | Out-Null
}

$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# Write approval record: outputs/TC-XXX/phase-N-name/approval.json
$approvalRecord = @{
    test_case_id   = $tcId
    phase          = $Phase
    phase_folder   = $phaseName
    phase_name     = $display
    decision       = $Decision
    decided_at     = $now
    reviewer_notes = if ($Reason) { $Reason } else { "No additional notes." }
    output_file    = "outputs/$tcId/$phaseName/output.md"
} | ConvertTo-Json -Depth 3

$approvalFile = Join-Path $phaseDir "approval.json"
$approvalRecord | Out-File -FilePath $approvalFile -Encoding utf8
Write-Host "  Approval recorded: outputs\$tcId\$phaseName\approval.json" -ForegroundColor DarkGray

# Update TC-level phase-status.json
$tcStatusFile = Join-Path $Root "outputs\$tcId\phase-status.json"
if (-not (Test-Path $tcStatusFile)) {
    Write-Host "  Warning: $tcStatusFile not found -- approval saved but status not updated." -ForegroundColor Yellow
} else {
    $tcStatus  = Get-Content $tcStatusFile -Raw | ConvertFrom-Json
    $phaseKey  = "$Phase"
    $phaseObj  = $tcStatus.phases.$phaseKey

    if (-not $phaseObj) {
        Write-Error "Phase $Phase not found in $tcStatusFile"
        exit 1
    }

    if ($Decision -eq "APPROVED") {
        $tcStatus.phases.$phaseKey.status = "APPROVED"
        $tcStatus.phases.$phaseKey | Add-Member -MemberType NoteProperty -Name "approved_at" -Value $now -Force

        if ($tcStatus.current_phase -eq $Phase -and $Phase -lt 8) {
            $tcStatus.current_phase = $Phase + 1
        }
        if ($Phase -eq 8) {
            $tcStatus | Add-Member -MemberType NoteProperty -Name "pipeline_status"       -Value "COMPLETE" -Force
            $tcStatus | Add-Member -MemberType NoteProperty -Name "pipeline_completed_at" -Value $now       -Force
            # Also update master status
            if (Test-Path $MasterStatusFile) {
                try {
                    $master = Get-Content $MasterStatusFile -Raw | ConvertFrom-Json
                    if ($master.test_cases.PSObject.Properties[$tcId]) {
                        $master.test_cases.$tcId.pipeline_status = "COMPLETE"
                        $master.test_cases.$tcId | Add-Member -MemberType NoteProperty -Name "completed_at" -Value $now -Force
                        $master | Add-Member -MemberType NoteProperty -Name "last_updated" -Value $now -Force
                        $master | ConvertTo-Json -Depth 10 | Out-File -FilePath $MasterStatusFile -Encoding utf8
                    }
                } catch { }
            }
        }

        Write-Host ""
        Write-Host "  [OK] $tcId Phase $Phase ($display) -- APPROVED" -ForegroundColor Green
        if ($Phase -lt 8) {
            $nextFolder = $PhaseFolders[$Phase + 1]
            $nextName   = $PhaseDisplayNames[$Phase + 1]
            Write-Host "  -> Next: Phase $($Phase + 1) ($nextName)" -ForegroundColor Cyan
            Write-Host "     Output will go to: outputs\$tcId\$nextFolder\" -ForegroundColor DarkGray
        } else {
            Write-Host "  -> Pipeline COMPLETE for $tcId. Create GitHub PR with docs/$tcId/pr-description.md" -ForegroundColor Green
        }
    } else {
        $tcStatus.phases.$phaseKey.status = "REJECTED"
        $tcStatus.phases.$phaseKey | Add-Member -MemberType NoteProperty -Name "rejected_at" -Value $now -Force
        if ($Reason) {
            $tcStatus.phases.$phaseKey | Add-Member -MemberType NoteProperty -Name "rejection_reason" -Value $Reason -Force
        }

        Write-Host ""
        Write-Host "  [!!] $tcId Phase $Phase ($display) -- REJECTED" -ForegroundColor Red
        if ($Reason) {
            Write-Host "  Reason: $Reason" -ForegroundColor Yellow
        }
        Write-Host "  -> Re-run Phase $Phase agent incorporating the rejection feedback." -ForegroundColor Yellow
    }

    $tcStatus | ConvertTo-Json -Depth 10 | Out-File -FilePath $tcStatusFile -Encoding utf8
}

Write-Host ""
& (Join-Path $PSScriptRoot "show-phase-status.ps1") -TestCase $tcId
