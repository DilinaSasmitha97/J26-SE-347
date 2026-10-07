@echo off
cd /d "%~dp0"
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env copy .env.example .env
echo Starting NL-to-SQL service on http://localhost:8000/docs
python run_server.py
echo.
echo Server stopped. See any error above.
pause
