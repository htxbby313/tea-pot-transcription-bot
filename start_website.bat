@echo off
title Tea Pot Landing Page Server
echo =======================================================
echo     🫖 TEA POT TRANSCRIPTION BOT — LANDING PAGE
echo =======================================================
echo.
echo Launching local preview on http://localhost:8080 ...
echo Press Ctrl+C in this window to stop the server.
echo.

cd /d "%~dp0web"
start http://localhost:8080
python -m http.server 8080
pause
