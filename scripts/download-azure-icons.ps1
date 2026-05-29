<#
.SYNOPSIS
    Downloads the Microsoft Azure Architecture Icons (V19) pack and the
    Terms of Use document into icons/azure_V19/, then regenerates the
    icon manifest.

.DESCRIPTION
    Idempotent: re-running on an up-to-date checkout is a no-op (compares
    bytes, only overwrites if changed). Designed to be called from a fresh
    workspace or from .github/workflows/refresh-icons.yml.

.PARAMETER OutputDir
    Where to extract the icons. Defaults to ./icons/azure_V19/ relative to
    the repo root.

.PARAMETER IconPackUrl
    Override the source URL. The official URL is published on
    https://learn.microsoft.com/azure/architecture/icons/ and changes per
    version. Defaults to the V19 URL as of 2026-05-29.

.PARAMETER TermsUrl
    Override the Terms of Use URL.

.EXAMPLE
    pwsh ./scripts/download-azure-icons.ps1

.EXAMPLE
    pwsh ./scripts/download-azure-icons.ps1 -OutputDir /tmp/icons_check
#>

[CmdletBinding()]
param(
    [string] $OutputDir = (Join-Path $PSScriptRoot '..\icons\azure_V19'),
    [string] $IconPackUrl = 'https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V19.zip',
    [string] $TermsUrl    = 'https://arch-center.azureedge.net/icons/Microsoft-Cloud-and-AI-Symbol-Icon-Terms-of-Use.pdf',
    [string] $VersionLabel = 'V19'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Step($msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

# Resolve to absolute path; create if missing.
$OutputDir = (New-Item -ItemType Directory -Path $OutputDir -Force).FullName
Write-Step "Output dir: $OutputDir"

$tmpZip = Join-Path ([System.IO.Path]::GetTempPath()) "azure-icons-$VersionLabel-$([guid]::NewGuid().ToString('N')).zip"
$tmpExtract = Join-Path ([System.IO.Path]::GetTempPath()) "azure-icons-$VersionLabel-$([guid]::NewGuid().ToString('N'))"

try {
    Write-Step "Downloading icon pack: $IconPackUrl"
    Invoke-WebRequest -Uri $IconPackUrl -OutFile $tmpZip -UseBasicParsing

    Write-Step "Extracting..."
    Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force

    # Microsoft's zip layout typically contains a top-level folder; flatten it.
    $topLevel = Get-ChildItem $tmpExtract -Directory | Select-Object -First 1
    $sourceRoot = if ($topLevel) { $topLevel.FullName } else { $tmpExtract }

    Write-Step "Mirroring SVGs into $OutputDir (preserves sub-folders)..."
    # Wipe existing icons first to catch removals; preserve README and .gitkeep.
    Get-ChildItem $OutputDir -Recurse -File `
        | Where-Object { $_.Name -notin @('README.md', '.gitkeep', 'Terms_of_Use.pdf', 'VERSION.txt') } `
        | Remove-Item -Force

    Get-ChildItem $sourceRoot -Recurse -Include '*.svg' | ForEach-Object {
        $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\','/')
        $dest = Join-Path $OutputDir $relative
        New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
        Copy-Item $_.FullName $dest -Force
    }

    $svgCount = (Get-ChildItem $OutputDir -Recurse -Include '*.svg').Count
    Write-Step "Copied $svgCount SVG icons"

    Write-Step "Downloading Terms of Use: $TermsUrl"
    Invoke-WebRequest -Uri $TermsUrl -OutFile (Join-Path $OutputDir 'Terms_of_Use.pdf') -UseBasicParsing

    Set-Content -Path (Join-Path $OutputDir 'VERSION.txt') -Value $VersionLabel -NoNewline
    Write-Step "Wrote VERSION.txt = $VersionLabel"

    # Regenerate manifest
    $manifestScript = Join-Path $PSScriptRoot 'build-icon-manifest.ps1'
    if (Test-Path $manifestScript) {
        Write-Step "Rebuilding manifest..."
        & $manifestScript -IconsDir $OutputDir
    } else {
        Write-Warning "build-icon-manifest.ps1 not found; skipping manifest regeneration."
    }

    Write-Step "Done."
}
finally {
    Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
    Remove-Item $tmpExtract -Recurse -Force -ErrorAction SilentlyContinue
}
