@echo off
setlocal

cd /d "%~dp0"
set "VIDEEP_PYTHON=%~dp0.venv\Scripts\python.exe"
set "VIDEEP_EXAMPLE_DIR=%~dp0examples\yolo_vehicle"
set "VIDEEP_CONFIG=%VIDEEP_EXAMPLE_DIR%\pipeline.json"
set "VIDEEP_PLUGIN_CONFIG=%VIDEEP_EXAMPLE_DIR%\config.json"
set "VIDEEP_DETECTOR=%VIDEEP_EXAMPLE_DIR%\models\yolo-vehicle.pt"
set "PYTHONUTF8=1"
set "YOLO_CONFIG_DIR=%~dp0.ultralytics"

rem PyNvVideoCodec 2.2.2 Windows binary links against CUDA Runtime 12.
if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\cudart64_12.dll" (
    set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6"
)

if not "%~1"=="" set "VIDEEP_CONFIG=%~f1"

if not exist "%VIDEEP_PYTHON%" (
    echo [ERROR] Python virtual environment not found: "%VIDEEP_PYTHON%"
    echo Run: uv sync --extra dev --extra nvidia --extra vehicle-example
    exit /b 1
)

if not exist "%VIDEEP_CONFIG%" (
    echo [ERROR] Pipeline configuration not found: "%VIDEEP_CONFIG%"
    echo Copy and edit the example first:
    echo   copy examples\yolo_vehicle\pipeline.example.json examples\yolo_vehicle\pipeline.json
    exit /b 1
)

if not exist "%VIDEEP_PLUGIN_CONFIG%" (
    echo [ERROR] Vehicle plugin configuration not found: "%VIDEEP_PLUGIN_CONFIG%"
    echo Copy and edit the example first:
    echo   copy examples\yolo_vehicle\config.example.json examples\yolo_vehicle\config.json
    exit /b 1
)

if not exist "%VIDEEP_DETECTOR%" (
    echo [ERROR] YOLO detector model not found: "%VIDEEP_DETECTOR%"
    exit /b 1
)

if not exist "%YOLO_CONFIG_DIR%" mkdir "%YOLO_CONFIG_DIR%" >nul 2>&1

"%VIDEEP_PYTHON%" -c "import PyNvVideoCodec, torch, ultralytics; assert torch.version.cuda is not None, 'CPU-only PyTorch is installed'; assert torch.cuda.is_available(), 'CUDA device is unavailable'"
if errorlevel 1 (
    echo [ERROR] NVIDIA or vehicle-example dependency validation failed.
    echo Run: uv sync --extra dev --extra nvidia --extra vehicle-example
    echo Check the Python error printed above for the exact cause.
    exit /b 1
)

echo Starting YOLO vehicle example...
echo Pipeline config: "%VIDEEP_CONFIG%"
"%VIDEEP_PYTHON%" -m videep.cli start --config "%VIDEEP_CONFIG%" --stats-interval 5
set "VIDEEP_EXIT_CODE=%ERRORLEVEL%"

if not "%VIDEEP_EXIT_CODE%"=="0" (
    echo Example pipeline exited with error code %VIDEEP_EXIT_CODE%.
)

exit /b %VIDEEP_EXIT_CODE%
