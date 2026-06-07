# scripts/finish-fix.ps1
# Usage: .\scripts\finish-fix.ps1
#
# Merges the current fix/* branch into main, pushes, and deletes the fix branch.
# Run this only after confirming the fix works correctly.

$branch = git rev-parse --abbrev-ref HEAD
if (-not $branch.StartsWith("fix/")) {
    Write-Host "ERROR: Current branch is '$branch'. Must be on a fix/* branch." -ForegroundColor Red
    exit 1
}

Write-Host "Merging '$branch' into main..." -ForegroundColor Cyan

# Switch to main and merge
git checkout main
if (-not $?) { exit 1 }

git pull origin main
if (-not $?) { exit 1 }

git merge --no-ff $branch -m "Merge $branch into main"
if (-not $?) {
    Write-Host "Merge conflict. Resolve conflicts, then push manually." -ForegroundColor Red
    exit 1
}

git push origin main
if (-not $?) { exit 1 }

# Delete fix branch locally and on remote
git branch -d $branch
git push origin --delete $branch 2>$null

Write-Host ""
Write-Host "Done. '$branch' merged and deleted." -ForegroundColor Green
