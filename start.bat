@echo off
REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b
)

echo Checking virtual environment...
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b
    )
)

echo Activating virtual environment...
call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment.
    pause
    exit /b
)

echo Installing dependencies...
python -m pip install -r requirements.txt

echo Starting application...
streamlit run main.py

pause
