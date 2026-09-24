@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js 20.3 or newer is required. Install Node.js, then reopen this file.
  pause
  exit /b 1
)
node scripts/start.mjs
if errorlevel 1 pause
