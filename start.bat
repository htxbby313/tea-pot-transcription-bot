@echo off
setlocal enabledelayedexpansion

title Tea Pot Transcription Bot
echo =======================================================
echo        🫖 TEA POT TRANSCRIPTION BOT LAUNCHER
echo =======================================================

echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in your PATH!
    echo Please download and install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: 2. Check or Create Virtual Environment
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 3. Check or Create .env
if not exist ".env" (
    echo [!] No .env file found. Creating from .env.example...
    copy .env.example .env >nul
    echo.
    echo =======================================================
    echo [ACTION REQUIRED] Please edit the '.env' file with:
    echo  1. Your DISCORD_BOT_TOKEN
    echo  2. Your OPENAI_API_KEY or DEEPGRAM_API_KEY
    echo =======================================================
    echo.
    notepad .env
    echo Press any key once you have saved your keys in .env...
    pause >nul
)

:: 4. Install / Update Dependencies
echo [2/3] Verifying and installing dependencies...
.venv\Scripts\pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: 5. Run the Bot
echo [3/3] Starting Transcriber Bot...
echo.
.venv\Scripts\python bot.py

echo.
echo [Bot Stopped]
pause
