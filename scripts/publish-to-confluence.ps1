#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Publish DocSync SDLC phase documents for a test case to Confluence Cloud.

.DESCRIPTION
    Reads docs/<TestCase>/*.md and creates/updates Confluence pages via the
    Confluence REST API v2. Uses credentials from environment variables.

    Required environment variables:
      CONFLUENCE_BASE_URL   â€” e.g. https://myorg.atlassian.net
      CONFLUENCE_USER       â€” Atlassian account email
      CONFLUENCE_API_TOKEN  â€” Atlassian API token (never hardcode)

.EXAMPLE
    scripts\publish-to-confluence.ps1 -TestCase TC-003 -SpaceKey DS
    scripts\publish-to-confluence.ps1 -TestCase TC-003 -SpaceKey DS -ParentPageId 123456
    scripts\publish-to-confluence.ps1 -TestCase TC-003 -SpaceKey DS -DryRun
#>

param(
    [Parameter(Mandatory)]
    [string]$TestCase,

    [Parameter(Mandatory)]
    [string]$SpaceKey,

    [string]$ParentPageId = "",
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root    = Split-Path $PSScriptRoot -Parent
$DocsDir = Join-Path $Root "docs\$TestCase"

# â”€â”€ Load credentials from environment (never hardcode) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$BaseUrl = $env:CONFLUENCE_BASE_URL
$User    = $env:CONFLUENCE_USER
$Token   = $env:CONFLUENCE_API_TOKEN

if (-not $BaseUrl -or -not $User -or -not $Token) {
    Write-Error @"
Missing required environment variables.
Set the following before running:
  CONFLUENCE_BASE_URL   â€” e.g. https://myorg.atlassian.net
  CONFLUENCE_USER       â€” your Atlassian email
  CONFLUENCE_API_TOKEN  â€” your Atlassian API token
"@
    exit 1
}

# Strip trailing slash
$BaseUrl = $BaseUrl.TrimEnd("/")

# â”€â”€ Build Basic Auth header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$credBytes  = [System.Text.Encoding]::UTF8.GetBytes("${User}:${Token}")
$b64Cred    = [Convert]::ToBase64String($credBytes)
$AuthHeader = @{ Authorization = "Basic $b64Cred" }

# â”€â”€ Phase document map â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$PhasePages = @(
    @{ Title = "Requirements";        File = "requirements.md"   }
    @{ Title = "Architecture";        File = "architecture.md"   }
    @{ Title = "Design Review";       File = "design-review.md"  }
    @{ Title = "Implementation Plan"; File = "impl-plan.md"      }
    @{ Title = "Code Review";         File = "code-review.md"    }
    @{ Title = "Verification";        File = "verification.md"   }
    @{ Title = "PR Description";      File = "pr-description.md" }
)

# â”€â”€ Helper: convert Markdown to basic Confluence wiki markup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function ConvertTo-ConfluenceWiki([string]$md) {
    # Very lightweight Markdown â†’ Confluence wiki conversion.
    # For production use, prefer a full markdown-to-confluence library.
    $out = $md
    # Headings
    $out = $out -replace '(?m)^#{6}\s+(.+)$', 'h6. $1'
    $out = $out -replace '(?m)^#{5}\s+(.+)$', 'h5. $1'
    $out = $out -replace '(?m)^#{4}\s+(.+)$', 'h4. $1'
    $out = $out -replace '(?m)^#{3}\s+(.+)$', 'h3. $1'
    $out = $out -replace '(?m)^#{2}\s+(.+)$', 'h2. $1'
    $out = $out -replace '(?m)^#{1}\s+(.+)$', 'h1. $1'
    # Bold / italic
    $out = $out -replace '\*\*(.+?)\*\*', '*$1*'
    $out = $out -replace '_(.+?)_', '_$1_'
    # Inline code
    $out = $out -replace '`(.+?)`', '{{$1}}'
    # Horizontal rule
    $out = $out -replace '(?m)^---+$', '----'
    # Tables â€” pass-through (Confluence wiki tables use | already)
    return $out
}

# â”€â”€ Helper: search for existing page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function Find-Page([string]$title, [string]$spaceKey) {
    $encodedTitle = [Uri]::EscapeDataString($title)
    $url = "$BaseUrl/wiki/rest/api/content?title=$encodedTitle&spaceKey=$spaceKey&type=page&expand=version"
    try {
        $resp = Invoke-RestMethod -Uri $url -Headers $AuthHeader -Method GET
        return $resp.results | Select-Object -First 1
    } catch {
        return $null
    }
}

# â”€â”€ Helper: create page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function New-ConfluencePage([string]$title, [string]$body, [string]$spaceKey, [string]$parentId) {
    $url  = "$BaseUrl/wiki/rest/api/content"
    $ancestors = if ($parentId) { @(@{ id = $parentId }) } else { @() }

    $payload = @{
        type    = "page"
        title   = $title
        space   = @{ key = $spaceKey }
        ancestors = $ancestors
        body    = @{
            wiki = @{
                value          = $body
                representation = "wiki"
            }
        }
    } | ConvertTo-Json -Depth 10

    $resp = Invoke-RestMethod -Uri $url -Headers ($AuthHeader + @{ "Content-Type" = "application/json" }) `
        -Method POST -Body $payload
    return $resp
}

# â”€â”€ Helper: update page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function Update-ConfluencePage([string]$pageId, [string]$title, [string]$body, [int]$currentVersion) {
    $url = "$BaseUrl/wiki/rest/api/content/$pageId"

    $payload = @{
        type    = "page"
        title   = $title
        version = @{ number = ($currentVersion + 1) }
        body    = @{
            wiki = @{
                value          = $body
                representation = "wiki"
            }
        }
    } | ConvertTo-Json -Depth 10

    $resp = Invoke-RestMethod -Uri $url -Headers ($AuthHeader + @{ "Content-Type" = "application/json" }) `
        -Method PUT -Body $payload
    return $resp
}

# â”€â”€ Main: create/update parent page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$parentTitle = "DocSync SDLC â€” $TestCase"
Write-Host ""
Write-Host "  Publishing to Confluence" -ForegroundColor Cyan
Write-Host "  Space   : $SpaceKey" -ForegroundColor White
Write-Host "  TC      : $TestCase" -ForegroundColor White
if ($DryRun) { Write-Host "  DRY RUN â€” no writes" -ForegroundColor Yellow }
Write-Host ""

$parentId = $ParentPageId

if (-not $DryRun) {
    $existing = Find-Page $parentTitle $SpaceKey
    if ($existing) {
        Write-Host "  [~] Parent page exists (id=$($existing.id))" -ForegroundColor Yellow
        $parentId = $existing.id
    } else {
        Write-Host "  [+] Creating parent page: $parentTitle" -ForegroundColor Green
        $created = New-ConfluencePage -title $parentTitle -body "h1. DocSync SDLC â€” $TestCase`n`nThis page contains all SDLC phase artifacts for test case $TestCase." -spaceKey $SpaceKey -parentId $ParentPageId
        $parentId = $created.id
        Write-Host "      Created id: $parentId" -ForegroundColor DarkGray
    }
}

# â”€â”€ Publish each phase page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$results = @()
foreach ($page in $PhasePages) {
    $filePath  = Join-Path $DocsDir $page.File
    $pageTitle = "DocSync SDLC â€” $TestCase â€” $($page.Title)"

    if (-not (Test-Path $filePath)) {
        Write-Host "  [!] Missing: $($page.File) â€” skipped" -ForegroundColor DarkYellow
        $results += [PSCustomObject]@{ Title = $pageTitle; Status = "SKIPPED"; Id = "" }
        continue
    }

    $mdContent   = Get-Content $filePath -Raw
    $wikiContent = ConvertTo-ConfluenceWiki $mdContent

    if ($DryRun) {
        Write-Host "  [dry] Would publish: $pageTitle" -ForegroundColor DarkGray
        $results += [PSCustomObject]@{ Title = $pageTitle; Status = "DRY_RUN"; Id = "" }
        continue
    }

    try {
        $existing = Find-Page $pageTitle $SpaceKey
        if ($existing) {
            $ver = $existing.version.number
            Update-ConfluencePage -pageId $existing.id -title $pageTitle -body $wikiContent -currentVersion $ver | Out-Null
            Write-Host "  [~] Updated : $pageTitle (id=$($existing.id))" -ForegroundColor Yellow
            $results += [PSCustomObject]@{ Title = $pageTitle; Status = "UPDATED"; Id = $existing.id }
        } else {
            $created = New-ConfluencePage -title $pageTitle -body $wikiContent -spaceKey $SpaceKey -parentId $parentId
            Write-Host "  [+] Created : $pageTitle (id=$($created.id))" -ForegroundColor Green
            $results += [PSCustomObject]@{ Title = $pageTitle; Status = "CREATED"; Id = $created.id }
        }
    } catch {
        $errMsg = $_.Exception.Message
        Write-Host "  [X] Failed  : $pageTitle â€” $errMsg" -ForegroundColor Red
        $results += [PSCustomObject]@{ Title = $pageTitle; Status = "FAILED"; Id = "" }
    }
}

# â”€â”€ Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
$created  = ($results | Where-Object { $_.Status -eq "CREATED" }).Count
$updated  = ($results | Where-Object { $_.Status -eq "UPDATED" }).Count
$failed   = ($results | Where-Object { $_.Status -eq "FAILED" }).Count
$skipped  = ($results | Where-Object { $_.Status -eq "SKIPPED" }).Count

Write-Host ""
Write-Host "  Confluence Publish Complete" -ForegroundColor Cyan
Write-Host "  Created  : $created" -ForegroundColor Green
Write-Host "  Updated  : $updated" -ForegroundColor Yellow
Write-Host "  Skipped  : $skipped" -ForegroundColor DarkYellow
if ($failed -gt 0) {
    Write-Host "  Failed   : $failed" -ForegroundColor Red
}
Write-Host ""

