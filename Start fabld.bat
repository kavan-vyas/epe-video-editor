@echo off
rem Double-click this file to start fabld on Windows. A browser opens automatically.
cd /d "%~dp0"
echo.
echo   Starting fabld ...
echo.

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo   fabld needs one free helper program - ffmpeg - that isn't installed yet.
  echo   Copy-paste this line into a Command Prompt window and press Enter:
  echo.
  echo       winget install ffmpeg
  echo.
  echo   Then double-click this file again.
  pause
  exit /b 1
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3 server.py
) else (
  python server.py
)
if errorlevel 1 (
  echo.
  echo   Python 3 was not found. Install it from https://www.python.org/downloads/
  echo   and tick "Add python.exe to PATH" during setup. Then try again.
  pause
)
