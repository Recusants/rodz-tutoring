# Rodz Tutoring - 1-Click Push to GitHub, Docker Hub & AWS (PowerShell)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  RODZ TUTORING - 1-CLICK GITHUB, DOCKER HUB & AWS PUSH" -ForegroundColor Cyan
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

# 3. Determine active branch
$currentBranch = (git branch --show-current 2>$null)
if (!$currentBranch) { $currentBranch = "main" }
Write-Host "[*] Active branch: $currentBranch" -ForegroundColor Gray

# 4. Version Management
$currVer = "1.0.0"
if (Test-Path "version.txt") {
    $currVer = (Get-Content "version.txt").Trim().TrimStart('v')
}
$parts = $currVer.Split('.')
if ($parts.Length -eq 3) {
    $nextVer = "$($parts[0]).$($parts[1]).$([int]$parts[2] + 1)"
} else {
    $nextVer = "1.0.1"
}

Write-Host "Current Version : $currVer" -ForegroundColor White
Write-Host "Suggested Next  : $nextVer" -ForegroundColor White
$userVer = Read-Host "Enter release version [Press Enter for $nextVer]"
if (!$userVer) { $userVer = $nextVer }
$cleanVer = $userVer.Trim().TrimStart('v')
$tagName = "v$cleanVer"
$cleanVer | Set-Content "version.txt"

# 5. Commit message
$msg = Read-Host "Enter commit message (Leave blank for 'Release $tagName')"
if (!$msg) {
    $dateStr = Get-Date -Format "yyyy-MM-dd HH:mm"
    $msg = "Release $tagName - $dateStr"
}

# 6. Run automated tests before push
Write-Host "`n[*] Running automated test suite before push..." -ForegroundColor Yellow
if (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" manage.py test
} elseif (Test-Path "venv\Scripts\python.exe") {
    & "venv\Scripts\python.exe" manage.py test
} else {
    python manage.py test
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Tests failed! Aborting push to protect production." -ForegroundColor Red
    pause
    return
}
Write-Host "[OK] All tests passed!" -ForegroundColor Green

# 7. Stage and commit
Write-Host "[*] Staging and committing..." -ForegroundColor Yellow
git add -A
git commit -m $msg

# 8. Create Tag and Push
Write-Host "[*] Tagging release as $tagName..." -ForegroundColor Yellow
git tag -fa $tagName -m "Release $tagName"

Write-Host "[*] Pushing branch and tag to GitHub..." -ForegroundColor Yellow
git push origin $currentBranch $tagName --force

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host "  SUCCESSFULLY PUSHED TO GITHUB!" -ForegroundColor Green
    Write-Host "  1. GitHub Actions triggered" -ForegroundColor Green
    Write-Host "  2. Building & publishing :latest and :$tagName to Docker Hub" -ForegroundColor Green
    Write-Host "  3. Deploying updated container to AWS EC2!" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Git push encountered an issue." -ForegroundColor Red
}
pause
