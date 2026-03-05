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
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%v\python.exe"
        echo Found Python at: !PYTHON_CMD!
        goto :FoundPython
    )
    if exist "%ProgramFiles%\Python%%v\python.exe" (
        set "PYTHON_CMD=%ProgramFiles%\Python%%v\python.exe"
        echo Found Python at: !PYTHON_CMD!
        goto :FoundPython
    )
    if exist "C:\Python%%v\python.exe" (
        set "PYTHON_CMD=C:\Python%%v\python.exe"
        echo Found Python at: !PYTHON_CMD!
        goto :FoundPython
    )
)

echo.
echo [ERROR] Python not found!
echo Please install Python 3.8+ from https://www.python.org/downloads/
pause
exit /b

:FoundPython
echo Using Python: !PYTHON_CMD!

echo.
echo Checking virtual environment...
if not exist ".venv" (
    echo Creating virtual environment...
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

REM Check if requirements were already installed successfully to avoid redundant slow checks
set "REQ_HASH_FILE=.venv\.req_hash"
set "CURRENT_REQ="
for /f "tokens=*" %%a in (requirements.txt) do set "CURRENT_REQ=!CURRENT_REQ!%%a"

if exist "!REQ_HASH_FILE!" (
    set /p STORED_REQ=<"!REQ_HASH_FILE!"
    if "!STORED_REQ!"=="!CURRENT_REQ!" (
        echo.
        echo Dependencies are up to date, skipping installation.
        goto :StartApp
    )
)

echo.
echo [NOTICE] Installing/Updating dependencies...
echo (Using Aliyun Mirror with 100s timeout to prevent ReadTimeoutError)

REM Primary: Aliyun, Fallback: Tsinghua
python -m pip install --upgrade pip --default-timeout=100 -i https://mirrors.aliyun.com/pypi/simple/
python -m pip install -r requirements.txt --default-timeout=100 -i https://mirrors.aliyun.com/pypi/simple/

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Aliyun mirror failed, trying Tsinghua mirror...
    python -m pip install -r requirements.txt --default-timeout=100 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

if %errorlevel% equ 0 (
    echo !CURRENT_REQ! > "!REQ_HASH_FILE!"
) else (
    echo.
    echo [ERROR] Failed to install dependencies. 
    echo Please check your internet connection or manually run:
    echo pip install -r requirements.txt
    pause
    exit /b
)

:StartApp
echo.
echo Starting application...
streamlit run main.py

pause
