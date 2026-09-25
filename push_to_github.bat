@echo off
setlocal enabledelayedexpansion
title Rodz Tutoring - 1-Click Push to GitHub
echo ========================================================
echo   RODZ TUTORING - 1-CLICK PUSH TO GITHUB
echo ========================================================
echo.

REM 1. Initialize git if needed
if not exist ".git" (
    echo [*] Initializing Git repository...
    git init
    git branch -M main
)

REM 2. Check remote origin
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] No remote 'origin' detected for this repository.
    set /p REPO_URL="Enter your GitHub repository URL (e.g. https://github.com/YourUsername/rodz-tutoring.git): "
    if not "!REPO_URL!"=="" (
        git remote add origin !REPO_URL!
        echo [*] Remote origin set to !REPO_URL!
    ) else (
        echo [ERROR] No remote specified. Cannot push.
        pause
        exit /b 1
    )
)

REM 3. Prompt for commit message
echo.
set /p COMMIT_MSG="Enter commit message (Press Enter for auto-message): "
if "!COMMIT_MSG!"=="" (
    for /f "tokens=1-4 delims=/ " %%a in ('date /t') do (set MYDATE=%%a-%%b-%%c)
    for /f "tokens=1-2 delims=: " %%a in ('time /t') do (set MYTIME=%%a:%%b)
    set COMMIT_MSG=Update Rodz Tutoring Platform - !MYDATE! !MYTIME!
)

REM 4. Stage and commit
echo.
echo [*] Staging files...
git add -A

echo [*] Committing: "!COMMIT_MSG!"...
git commit -m "!COMMIT_MSG!"

REM 5. Push to GitHub
echo.
echo [*] Pushing to GitHub (main)...
git push -u origin main

if errorlevel 1 (
    echo.
    echo [!] Push failed or remote branch requires pull first.
    echo [*] Attempting pull with rebase...
    git pull origin main --rebase
    echo [*] Retrying push...
    git push -u origin main
)

if errorlevel 0 (
    echo.
    echo ========================================================
    echo   SUCCESSFULLY PUSHED TO GITHUB!
    echo   GitHub Actions will now trigger Docker Hub build.
    echo ========================================================
) else (
    echo.
    echo [ERROR] Push failed. Check your GitHub permissions/credentials.
)

echo.
pause
