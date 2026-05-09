@echo off
REM ── LibreScore Desktop Launcher (Windows) ──

cd /d "%~dp0"

REM Ensure uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Installing uv (Python package manager)...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo ERROR: uv installation failed. Please install manually:
        echo   https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
    echo uv installed successfully!
)

echo Starting LibreScore...
uv run dl_librescore_app.py
pause
