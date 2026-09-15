@echo off
echo Setting up Fellowship Eternal Tracker...

where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: 'uv' is not installed or not in your PATH.
    echo Please install it from https://docs.astral.sh/uv/
    pause
    exit /b 1
)

if not exist "config.json" (
    echo Copying config.example.json to config.json...
    copy config.example.json config.json
)

echo Syncing dependencies...
uv sync

echo Starting server...
uv run server.py
pause
