@echo off
title Rodz Tutoring - Local Dev Server
echo ========================================================
echo   RODZ TUTORING - 1-CLICK DEV LAUNCHER
echo ========================================================
echo.

REM 1. Check/Create Virtual Environment
if not exist ".venv\Scripts\activate.bat" (
    echo [1/5] Creating Python virtual environment in .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment. Ensure Python is installed.
        pause
        exit /b 1
    )
)

echo [2/5] Activating virtual environment...
call .venv\Scripts\activate.bat

REM 2. Ensure dependencies installed
echo [3/5] Verifying dependencies...
pip install -r requirements.txt --quiet

REM 3. Ensure .env exists
if not exist ".env" (
    echo [4/5] .env not found. Copying from .env.example...
    copy .env.example .env >nul
) else (
    echo [4/5] Found existing .env file.
)

REM 4. Run migrations & Seed
echo [5/5] Running migrations and verifying database...
python manage.py migrate --noinput
python manage.py seed_rodz

echo.
echo ========================================================
echo   SERVER STARTING AT http://127.0.0.1:8088/
echo   Admin login: admin@rodztutoring.co.za / RodzAdmin2026!
echo   Student login: student@rodztutoring.co.za / RodzStudent2026!
echo ========================================================
echo.

REM Open browser automatically
start http://127.0.0.1:8088/

REM Run development server
python manage.py runserver 127.0.0.1:8088

pause
