@echo off
setlocal
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\python.exe" (
  py -3.13 -m venv .venv || python -m venv .venv
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt

if not exist "frontend\node_modules" (
  pushd frontend
  call npm install --no-audit --no-fund
  popd
)

if not exist "frontend\dist" (
  pushd frontend
  call npm run build
  popd
)

start "" "http://127.0.0.1:8780/"
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8780
