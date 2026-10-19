@echo off
cd /d "%~dp0"
python app.py --open
if errorlevel 1 (
  echo Check the error above. Python 3.11+ must be on PATH; port 8765 must be free.
  pause
)
