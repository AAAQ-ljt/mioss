@echo off
setlocal
cd /d "%~dp0..\..\ComfyUI_windows_portable"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
".\python_embeded\python.exe" -s ComfyUI\main.py --windows-standalone-build --disable-auto-launch --listen 127.0.0.1 --port 8188
