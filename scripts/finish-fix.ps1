# scripts/finish-fix.ps1
# Usage: .\scripts\finish-fix.ps1 ["PR title"]
#
# Pushes the current fix/* branch and opens a Pull Request to main.
# Merge on GitHub after confirming the fix works.

param(
    [string]$Title = ""
)

$branch = git rev-parse --abbrev-ref HEAD
if (-not $branch.StartsWith("fix/")) {
    Write-Host "ERROR: Current branch is '$branch'. Must be on a fix/* branch." -ForegroundColor Red
    exit 1
}

# Derive default PR title from branch name
if ($Title -eq "") {
    $Title = $branch -replace "^fix/", "" -replace "-", " "
    $Title = "fix: $Title"
}

# Push fix branch to remote
git push -u origin $branch
if (-not $?) { exit 1 }

# Open PR to main
gh pr create --base main --head $branch --title $Title --body ""
if (-not $?) { exit 1 }

Write-Host ""
Write-Host "PR created. Review and merge on GitHub, then run:" -ForegroundColor Green
Write-Host "  git checkout main && git pull origin main && git branch -d $branch" -ForegroundColor Cyan
