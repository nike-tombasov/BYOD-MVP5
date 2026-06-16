@echo off
setlocal
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Creating Python 3.11 virtual environment...
  py -3.11 -m venv .venv || exit /b 1
)
call .venv\Scripts\activate.bat || exit /b 1
python -m pip install -r requirements.txt || exit /b 1
python byod_listener_loader.py %*
