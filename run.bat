@echo off
echo ========================================================
echo Starting CareSync PH - Online Clinic Booking System
echo ========================================================
echo.

if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
    echo Seeding database...
    python seed.py
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo Server starting at: http://127.0.0.1:8000
echo API Documentation at: http://127.0.0.1:8000/docs
echo Press CTRL+C to stop the server anytime.
echo.

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
