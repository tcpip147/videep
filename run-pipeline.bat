@echo off
setlocal

cd /d "%~dp0"
set "VIDEEP_PYTHON=%~dp0.venv\Scripts\python.exe"
set "VIDEEP_CONFIG=%~dp0pipeline.json"
set "PYTHONUTF8=1"

if not exist "%VIDEEP_PYTHON%" (
    echo [ERROR] Python virtual environment not found: "%VIDEEP_PYTHON%"
    echo Run: uv sync --extra dev
    exit /b 1
)

if not exist "%VIDEEP_CONFIG%" (
    echo [ERROR] Configuration file not found: "%VIDEEP_CONFIG%"
    exit /b 1
)

"%VIDEEP_PYTHON%" -c "from videep.backends.nvidia.backend import NvidiaBackend; assert NvidiaBackend.available()" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] NVIDIA backend dependency is not installed.
    echo Run: uv sync --extra dev --extra nvidia
    exit /b 1
)

echo Starting Videep pipeline...
"%VIDEEP_PYTHON%" -m videep.cli start --config "%VIDEEP_CONFIG%"
set "VIDEEP_EXIT_CODE=%ERRORLEVEL%"

if not "%VIDEEP_EXIT_CODE%"=="0" (
    echo Pipeline exited with error code %VIDEEP_EXIT_CODE%.
)

exit /b %VIDEEP_EXIT_CODE%
