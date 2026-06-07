# scripts/new-fix.ps1
# Usage: .\scripts\new-fix.ps1 <fix-name>
# Example: .\scripts\new-fix.ps1 rumble-endpoint
#
# Creates a new fix branch (fix/<name>) from the latest main and switches to it.

param(
    [Parameter(Mandatory=$true)]
    [string]$Name
)

$branch = "fix/$Name"

# Ensure we're starting from up-to-date main
git checkout main
if (-not $?) { exit 1 }

git pull origin main
if (-not $?) { exit 1 }

git checkout -b $branch
if (-not $?) { exit 1 }

Write-Host ""
Write-Host "Branch '$branch' created and checked out." -ForegroundColor Green
Write-Host "Make your changes, then run: .\scripts\finish-fix.ps1" -ForegroundColor Cyan
