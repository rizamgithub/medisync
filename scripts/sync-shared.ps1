#!/usr/bin/env pwsh
# Vendor the shared package (packages/shared/medisync_shared) into each Azure
# Function service so it ships inside that service's deploy bundle.
#
# Azure Functions deploys ONE folder per app and its Oryx remote build only
# pip-installs that app's requirements.txt -- it cannot see a sibling
# packages/ folder. So medisync_shared is copied in as source. The copies are
# gitignored (.gitignore: services/*/medisync_shared/); this script is the
# supported way to (re)create them.
#
# Run this:
#   * after cloning the repo, before `uv run pytest` / `func start`
#   * after editing anything under packages/shared/
#   * immediately before `func azure functionapp publish` (runbook 09, Step 4)
#
# Usage:  pwsh scripts/sync-shared.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "packages\shared\medisync_shared"

# Services that produce or consume MediSync domain events.
$targets = @("match", "inventory")

if (-not (Test-Path $source)) {
    throw "shared package not found at $source"
}

foreach ($svc in $targets) {
    $dest = Join-Path $repoRoot "services\$svc\medisync_shared"
    if (Test-Path $dest) {
        Remove-Item -Recurse -Force $dest
    }
    Copy-Item -Recurse $source $dest
    # Drop any __pycache__ that rode along from a stale source tree.
    Get-ChildItem -Path $dest -Recurse -Directory -Filter "__pycache__" |
        Remove-Item -Recurse -Force
    Write-Host "synced medisync_shared -> services/$svc/"
}

Write-Host "done."
