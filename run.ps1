Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting CareSync PH - Online Clinic Booking System" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & ".\.venv\Scripts\Activate.ps1"
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
    Write-Host "Seeding database..." -ForegroundColor Yellow
    python seed.py
} else {
    & ".\.venv\Scripts\Activate.ps1"
}

Write-Host ""
Write-Host "Server URL: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Swagger Docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host "Press CTRL+C in this terminal to stop the server anytime." -ForegroundColor Gray
Write-Host ""

& ".\.venv\Scripts\uvicorn.exe" app.main:app --reload --host 127.0.0.1 --port 8000
