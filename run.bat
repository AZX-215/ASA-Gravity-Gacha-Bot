@echo off
setlocal
cd /d %~dp0
if not exist venv\Scripts\python.exe py -3.11 -m venv venv
call venv\Scripts\activate.bat
python -m pip -q install -r requirements.txt
python main.py
