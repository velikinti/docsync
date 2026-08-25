param()
# PostToolUse hook: called after every Write/Edit tool use.
# Detects if a phase output document was written and archives it to:
#   outputs/TC-XXX/phase-N-name/output.md
# Also writes agent-log.json and updates the TC's phase-status.json.

$Root = Split-Path $PSScriptRoot -Parent
$MasterStatusFile = Join-Path $Root "outputs\phase-status.json"

# Map: relative doc path -> phase metadata
$PhaseOutputMap = @{
    "docs\requirements.md"   = @{phase=1; phaseName="phase-1-requirements";   displayName="Requirements"}
    "docs\architecture.md"   = @{phase=2; phaseName="phase-2-architecture";   displayName="Architecture"}
    "docs\design-review.md"  = @{phase=3; phaseName="phase-3-design-review";  displayName="Design Review"}
    "docs\impl-plan.md"      = @{phase=4; phaseName="phase-4-impl-planning";  displayName="Implementation Planning"}
    "docs\code-review.md"    = @{phase=6; phaseName="phase-6-code-review";    displayName="Code Review"}
    "docs\verification.md"   = @{phase=7; phaseName="phase-7-verification";   displayName="Verification"}
    "docs\pr-description.md" = @{phase=8; phaseName="phase-8-pr";             displayName="PR Creation"}
}

# Read hook event from stdin (JSON)
$inputJson = $null
try {
    $rawInput = [Console]::In.ReadToEnd()
    if ($rawInput -and $rawInput.Trim()) {
        $inputJson = $rawInput | ConvertFrom-Json
    }
} catch { }

$writtenFile = $null
if ($inputJson -and $inputJson.tool_name -in @("Write", "Edit")) {
    $writtenFile = $inputJson.tool_input.file_path
}
if (-not $writtenFile) { exit 0 }

# Normalize to relative path
$relPath = $writtenFile.Replace($Root, "").TrimStart("\", "/")
if (-not $PhaseOutputMap.ContainsKey($relPath)) { exit 0 }

$meta        = $PhaseOutputMap[$relPath]
$phaseNum    = $meta.phase
$phaseName   = $meta.phaseName
$displayName = $meta.displayName

# Determine active test case (default TC-001; read from master status if available)
$tcId = "TC-001"
if (Test-Path $MasterStatusFile) {
    try {
        $master = Get-Content $MasterStatusFile -Raw | ConvertFrom-Json
        if ($master.active_test_cases -and $master.active_test_cases.Count -gt 0) {
            $tcId = $master.active_test_cases[-1]
        }
    } catch { }
}

# Archive: outputs/TC-XXX/phase-N-name/output.md
$phaseDir = Join-Path $Root "outputs\$tcId\$phaseName"
if (-not (Test-Path $phaseDir)) {
    New-Item -ItemType Directory -Path $phaseDir -Force | Out-Null
}

$archivePath = Join-Path $phaseDir "output.md"
try {
    Copy-Item $writtenFile $archivePath -Force
    Write-Host "  [Hook] Archived -> outputs\$tcId\$phaseName\output.md" -ForegroundColor DarkGray
} catch {
    Write-Host "  [Hook] Warning: Could not archive output: $_" -ForegroundColor Yellow
}

$now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

# Write agent-log.json
$logFile = Join-Path $phaseDir "agent-log.json"
@{
    test_case_id    = $tcId
    phase           = $phaseNum
    phase_folder    = $phaseName
    phase_name      = $displayName
    output_file     = $relPath
    output_archived = "outputs/$tcId/$phaseName/output.md"
    written_at      = $now
    hook_trigger    = "PostToolUse:Write"
} | ConvertTo-Json -Depth 3 | Out-File -FilePath $logFile -Encoding utf8

# Update TC's phase-status.json -> PENDING_APPROVAL
$tcStatusFile = Join-Path $Root "outputs\$tcId\phase-status.json"
if (Test-Path $tcStatusFile) {
    try {
        $tcStatus = Get-Content $tcStatusFile -Raw | ConvertFrom-Json
        $key      = "$phaseNum"
        if ($tcStatus.phases.PSObject.Properties[$key]) {
            $current = $tcStatus.phases.$key.status
            if ($current -notin @("APPROVED", "PENDING_APPROVAL")) {
                $tcStatus.phases.$key.status = "PENDING_APPROVAL"
                $tcStatus.phases.$key | Add-Member -MemberType NoteProperty -Name "completed_at" -Value $now -Force
                $tcStatus | ConvertTo-Json -Depth 10 | Out-File -FilePath $tcStatusFile -Encoding utf8
                Write-Host "  [Hook] $tcId Phase $phaseNum status -> PENDING_APPROVAL" -ForegroundColor Yellow
            }
        }
    } catch { }
}

exit 0
