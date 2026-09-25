# Rodz Tutoring - 1-Click Push to GitHub (PowerShell)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  RODZ TUTORING - 1-CLICK PUSH TO GITHUB" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Initialize git if missing
if (!(Test-Path ".git")) {
    Write-Host "[*] Initializing Git repository..." -ForegroundColor Yellow
    git init
    git branch -M main
}

# 2. Check remote
$remoteUrl = git remote get-url origin 2>$null
if (!$remoteUrl) {
    Write-Host "[!] No remote 'origin' detected." -ForegroundColor Yellow
    $repo = Read-Host "Enter your GitHub repository URL (e.g. https://github.com/YourUsername/rodz-tutoring.git)"
    if ($repo) {
        git remote add origin $repo
    } else {
        Write-Host "[ERROR] Aborted: No remote specified." -ForegroundColor Red
        return
    }
}

# 3. Commit message
$msg = Read-Host "Enter commit message (Leave blank for auto-timestamped commit)"
if (!$msg) {
    $dateStr = Get-Date -Format "yyyy-MM-dd HH:mm"
    $msg = "Update Rodz Tutoring Platform - $dateStr"
}

# 4. Stage and commit
Write-Host "[*] Staging and committing..." -ForegroundColor Yellow
git add -A
git commit -m $msg

# 5. Push
Write-Host "[*] Pushing to GitHub (main)..." -ForegroundColor Yellow
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "  SUCCESSFULLY PUSHED TO GITHUB!" -ForegroundColor Green
    Write-Host "  GitHub Actions workflow is now triggering Docker build." -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host "[!] Pushing had issues. Trying git pull --rebase then push..." -ForegroundColor Yellow
    git pull origin main --rebase
    git push -u origin main
}
