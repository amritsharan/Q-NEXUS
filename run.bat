@echo off
REM run.bat - Setup virtualenv, install deps, and run the API server (Windows cmd)

IF "%1"=="-reinstall" (
  rmdir /s /q .venv
)

IF NOT EXIST .venv (
  echo Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Starting server (uvicorn on :8000)...
python -m uvicorn app:app --reload
