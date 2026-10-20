@echo off
cd /d "%~dp0backend"
if not exist .venv py -3 -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --host 127.0.0.1 --port 8000