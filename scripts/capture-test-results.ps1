param()
# PostToolUse hook: called after Bash tool use.
# Detects pytest output and saves structured test results to:
#   outputs/TC-XXX/phase-5-implementation/test-results.json
#   outputs/TC-XXX/phase-7-verification/test-results.json

$Root = Split-Path $PSScriptRoot -Parent
$MasterStatusFile = Join-Path $Root "outputs\phase-status.json"

# Read hook event from stdin
$inputJson = $null
try {
    $rawInput = [Console]::In.ReadToEnd()
    if ($rawInput -and $rawInput.Trim()) {
        $inputJson = $rawInput | ConvertFrom-Json
    }
} catch {
    exit 0
}

if (-not $inputJson) { exit 0 }
if ($inputJson.tool_name -ne "Bash") { exit 0 }

$command = $inputJson.tool_input.command
$output  = $inputJson.tool_output

if ($command -notmatch "pytest") { exit 0 }

# Parse pytest output
$passed  = 0
$failed  = 0
$errors  = 0
$total   = 0
$duration = ""
$coverageLines = @()

if ($output) {
    if ($output -match "(\d+) passed") { $passed = [int]$Matches[1] }
    if ($output -match "(\d+) failed") { $failed = [int]$Matches[1] }
    if ($output -match "(\d+) error")  { $errors = [int]$Matches[1] }
    $total = $passed + $failed + $errors
    if ($output -match "in ([\d.]+)s") { $duration = $Matches[1] + "s" }
    if ($output -match "TOTAL\s+\d+\s+\d+\s+(\d+)%") {
        $coverageLines += "TOTAL: $($Matches[1])%"
    }
}

$now     = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$verdict = if ($failed -eq 0 -and $errors -eq 0 -and $total -gt 0) { "PASS" } elseif ($total -eq 0) { "UNKNOWN" } else { "FAIL" }

$result = @{
    captured_at = $now
    command     = $command
    passed      = $passed
    failed      = $failed
    errors      = $errors
    total       = $total
    duration    = $duration
    verdict     = $verdict
    coverage    = $coverageLines
} | ConvertTo-Json -Depth 3

# Determine active TC
$tcId = "TC-001"
if (Test-Path $MasterStatusFile) {
    try {
        $master = Get-Content $MasterStatusFile -Raw | ConvertFrom-Json
        if ($master.active_test_cases -and $master.active_test_cases.Count -gt 0) {
            $tcId = $master.active_test_cases[-1]
        }
    } catch { }
}

# Save to phase-5-implementation and phase-7-verification under the active TC
$targetFolders = @("phase-5-implementation", "phase-7-verification")
foreach ($folder in $targetFolders) {
    $dir = Join-Path $Root "outputs\$tcId\$folder"
    if (Test-Path $dir) {
        $result | Out-File -FilePath (Join-Path $dir "test-results.json") -Encoding utf8
    }
}

if ($verdict -eq "PASS") {
    Write-Host "  [Hook] Test results captured: $passed/$total passed ($duration) -> $tcId" -ForegroundColor Green
} elseif ($verdict -eq "FAIL") {
    Write-Host "  [Hook] Test results captured: $failed FAILURES, $passed passed -> $tcId" -ForegroundColor Red
}

exit 0
