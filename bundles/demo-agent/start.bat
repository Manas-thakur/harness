@echo off
REM Agent Bundle Launcher: demo-agent

echo 🚀 Starting demo-agent...

REM Check for Ollama
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠ Ollama not found. Install from https://ollama.com
)

REM Launch the TUI (single interface)
set PYTHONPATH=%PYTHONPATH%;%~dp0
python -m harness.tui

pause
