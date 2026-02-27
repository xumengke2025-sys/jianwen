@echo off
setlocal EnableDelayedExpansion

echo Checking for Python...

REM 1. Try 'python' command
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :FoundPython
)

REM 2. Try 'py' launcher
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py"
    goto :FoundPython
)

REM 3. Search common installation paths
echo Python not in PATH, searching common locations...
for %%v in (313 312 311 310 39 38) do (
    REM User Local AppData
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        echo Found Python at: !PYTHON_CMD!
        goto :FoundPython
    )
    REM System Program Files
    if exist "%ProgramFiles%\Python%%v\python.exe" (
        set "PYTHON_CMD=%ProgramFiles%\Python%%v\python.exe"
        echo Found Python at: !PYTHON_CMD!
        goto :FoundPython
    )
    REM C Root
    if exist "C:\Python%%v\python.exe" (
        set "PYTHON_CMD=C:\Python%%v\python.exe"
        echo Found Python at: !PYTHON_CMD!
        goto :FoundPython
    )
)

echo.
echo [ERROR] Python not found!
echo Please install Python 3.8+ from https://www.python.org/downloads/
echo Note: During installation, check "Add Python to PATH" for best results.
echo.
pause
exit /b

:FoundPython
echo Using Python: !PYTHON_CMD!

echo.
echo Checking virtual environment...
if not exist ".venv" (
    echo Creating virtual environment in project directory...
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
)

echo Activating virtual environment...
call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b
)

echo.
echo Upgrading pip...
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

echo.
echo Installing dependencies locally (using Tsinghua Mirror)...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    echo Please check your internet connection.
    pause
    exit /b
)

echo.
echo Starting application...
streamlit run main.py

pause
