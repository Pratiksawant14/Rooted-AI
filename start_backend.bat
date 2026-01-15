@echo off
cd /d "%~dp0"
echo Starting Rooted AI Backend...
call backend\venv\Scripts\activate
python -m backend.main
pause
