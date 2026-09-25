# Rodz Tutoring - 1-Click Dev Launcher (PowerShell)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  RODZ TUTORING - 1-CLICK DEV LAUNCHER" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Virtual Environment
if (!(Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "[1/5] Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "[2/5] Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# 2. Dependencies
Write-Host "[3/5] Verifying dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet

# 3. .env check
if (!(Test-Path ".env")) {
    Write-Host "[4/5] Copying .env.example to .env..." -ForegroundColor Yellow
    Copy-Item .env.example .env
} else {
    Write-Host "[4/5] Found existing .env file." -ForegroundColor Green
}

# 4. Migrate and Seed
Write-Host "[5/5] Running migrations and seeding..." -ForegroundColor Yellow
python manage.py migrate --noinput
python manage.py seed_rodz

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  SERVER STARTING AT http://127.0.0.1:8000/" -ForegroundColor Green
Write-Host "  Admin login: admin@rodztutoring.co.za / RodzAdmin2026!" -ForegroundColor White
Write-Host "  Student login: student@rodztutoring.co.za / RodzStudent2026!" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""

Start-Process "http://127.0.0.1:8000/"
python manage.py runserver 127.0.0.1:8000
