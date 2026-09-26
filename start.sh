#!/usr/bin/env bash
set -e

echo "======================================================="
echo "       🫖 TEA POT TRANSCRIPTION BOT LAUNCHER"
echo "======================================================="

echo ""

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH."
    exit 1
fi

# 2. Check / Create venv
if [ ! -d ".venv" ]; then
    echo "[1/3] Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# 3. Check .env
if [ ! -f ".env" ]; then
    echo "[!] No .env file found. Copying .env.example..."
    cp .env.example .env
    echo "[ACTION REQUIRED] Please edit .env with your DISCORD_BOT_TOKEN and STT API Key."
    exit 1
fi

# 4. Install Dependencies
echo "[2/3] Installing dependencies..."
.venv/bin/pip install -r requirements.txt --quiet

# 5. Run Bot
echo "[3/3] Starting Bot..."
echo ""
.venv/bin/python bot.py
