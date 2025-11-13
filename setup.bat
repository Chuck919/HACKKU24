@echo off
REM Setup script for Any News application

echo ========================================
echo Any News - Setup Script
echo ========================================
echo.

REM Check if .env exists
if exist .env (
    echo [INFO] .env file already exists
) else (
    echo [SETUP] Creating .env file from template...
    copy .env.example .env
    echo [WARNING] Please edit .env and fill in your actual credentials!
    echo.
)

echo [SETUP] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [SETUP] Initializing database...
python -c "from app import app, db; app.app_context().push(); db.create_all()"

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env and add your credentials
echo 2. Run: python app.py
echo.
pause
