@echo off
REM Agent Bundle Launcher: demo-agent

echo 🚀 Starting demo-agent...

REM Check for Ollama
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠ Ollama not found. Install from https://ollama.com
)

REM Run agent
python -m harness.main ^
    --local ^
    --dashboard ^
    --bundle "%~dp0"

pause
