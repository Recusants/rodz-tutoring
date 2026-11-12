@echo off
TITLE Rodz Tutoring - 1-Click Push (GitHub, Docker Hub ^& AWS)
setlocal enabledelayedexpansion

echo ============================================================
echo    RODZ TUTORING - 1-CLICK GITHUB, DOCKER HUB ^& AWS DEPLOY
echo ============================================================
echo.

cd /d "%~dp0"

REM 1. Verify Git installation
where git >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git is not installed or not in PATH.
    echo Please install Git from https://git-scm.com/
    pause
    exit /b 1
)

REM 2. Verify or Initialize Git Repository
if not exist ".git" (
    echo [*] Initializing Git repository...
    git init
    git branch -M main
)

git remote get-url origin >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo [ACTION NEEDED] GitHub Remote URL not configured yet.
    echo ============================================================
    set /p "GIT_REMOTE=Enter your GitHub repository URL (e.g. https://github.com/Avail-Technologies-Pvt-Ltd/rodz-tutoring.git): "
    if not "!GIT_REMOTE!"=="" (
        git remote add origin !GIT_REMOTE!
        echo [OK] Remote origin set to: !GIT_REMOTE!
    ) else (
        echo [ERROR] No remote URL provided. Aborting.
        pause
        exit /b 1
    )
)

REM 3. Determine current branch
for /f "tokens=*" %%i in ('git branch --show-current 2^>nul') do set CURRENT_BRANCH=%%i
if "%CURRENT_BRANCH%"=="" set CURRENT_BRANCH=main
echo [INFO] Active Branch: %CURRENT_BRANCH%
echo.

REM 4. Version Management (version.txt)
set "CURR_VER=1.0.0"
if exist "version.txt" (
    set /p CURR_VER=<version.txt
    set "CURR_VER=!CURR_VER: =!"
)

REM Auto-calculate next patch version via PowerShell
for /f "tokens=*" %%v in ('powershell -NoProfile -Command "$v = '%CURR_VER%'.Trim().TrimStart('v'); $parts = $v.Split('.'); if ($parts.Length -eq 3) { $p = ([int]$parts[2]) + 1; $parts[0] + '.' + $parts[1] + '.' + $p } else { '1.0.1' }"') do set "NEXT_VER=%%v"

echo ------------------------------------------------------------
echo  VERSION RELEASE MANAGEMENT
echo ------------------------------------------------------------
echo  Current Version : %CURR_VER%
echo  Suggested Next  : %NEXT_VER%
echo.
set "USER_VER="
set /p "USER_VER=Enter release version [Press Enter for %NEXT_VER%]: "
if "!USER_VER!"=="" set "USER_VER=%NEXT_VER%"

REM Clean version string (remove leading v if entered)
for /f "tokens=*" %%v in ('powershell -NoProfile -Command "'!USER_VER!'.Trim().TrimStart('v')"') do set "CLEAN_VER=%%v"
set "TAG_NAME=v!CLEAN_VER!"

echo !CLEAN_VER!> "version.txt"
echo [INFO] Tag to be published: !TAG_NAME! (Docker Hub: !TAG_NAME! and latest)
echo.

REM 5. Check for uncommitted changes
git status --porcelain > "%TEMP%\git_status.txt"
set HAS_CHANGES=0
for %%A in ("%TEMP%\git_status.txt") do if %%~zA gtr 0 set HAS_CHANGES=1
del "%TEMP%\git_status.txt" 2>nul

REM 6. Commit Message
set "COMMIT_MSG=%*"
if not defined COMMIT_MSG (
    echo ------------------------------------------------------------
    echo  COMMIT MESSAGE
    echo ------------------------------------------------------------
    set /p "COMMIT_MSG=Enter commit message [Press Enter for 'Release !TAG_NAME!']: "
    if not defined COMMIT_MSG (
        for /f "tokens=*" %%T in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm'"') do set "NOW_TIME=%%T"
        set "COMMIT_MSG=Release !TAG_NAME! - !NOW_TIME!"
    )
)

echo.
echo ============================================================
echo [1/5] RUNNING AUTOMATED TEST SUITE BEFORE PUSH
echo ============================================================
call .venv\Scripts\activate.bat 2>nul || call venv\Scripts\activate.bat 2>nul
python manage.py test
if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo [ERROR] AUTOMATED TESTS FAILED!
    echo Push aborted to prevent releasing broken code.
    echo Please fix failing tests before pushing.
    echo ============================================================
    echo.
    pause
    exit /b 1
)
echo [OK] All automated tests passed successfully!
echo.

echo [2/5] Staging files...
git add -A

if %HAS_CHANGES% equ 1 (
    echo [3/5] Committing: "!COMMIT_MSG!"...
    git commit -m "!COMMIT_MSG!"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Commit failed.
        pause
        exit /b 1
    )
) else (
    echo [3/5] No uncommitted file changes; proceeding with release tag...
)

echo [4/5] Creating Git release tag: !TAG_NAME!...
git tag -fa !TAG_NAME! -m "Release !TAG_NAME!"

echo [5/5] Pushing code and tag to GitHub origin %CURRENT_BRANCH%...
git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push origin %CURRENT_BRANCH% !TAG_NAME! --force
if %ERRORLEVEL% neq 0 (
    echo [WARN] Initial push failed; retrying over HTTP/1.1...
    git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push origin %CURRENT_BRANCH% !TAG_NAME! --force
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================================
    echo [ERROR] Git push failed. Please check network/permissions.
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo                    PUSH SUCCESSFUL!
echo ============================================================
echo.
echo GitHub Actions is now:
echo   1. Building Docker image & publishing :latest and :!TAG_NAME! to Docker Hub
echo   2. Automatically deploying and updating AWS EC2 instance!
echo.

set "REPO_URL="
for /f "tokens=*" %%u in ('git remote get-url origin 2^>nul') do set "REPO_URL=%%u"
if defined REPO_URL (
    set "REPO_URL=!REPO_URL:.git=!"
    set "ACTIONS_URL=!REPO_URL!/actions"
) else (
    set "ACTIONS_URL=https://github.com"
)

echo Monitor your live workflow on GitHub:
echo   !ACTIONS_URL!
echo.

choice /C YN /T 6 /D N /M "Open GitHub Actions page in your web browser"
if !ERRORLEVEL! equ 1 start "" "!ACTIONS_URL!"

echo.
echo ============================================================
echo All done! Rodz Tutoring is building and deploying to AWS.
echo ============================================================
echo.
pause
