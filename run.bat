@echo off
setlocal
if not exist venv\Scripts\python.exe (
  py -3.11 -m venv venv || goto :eof
)
call venv\Scripts\activate.bat
python -m pip --disable-pip-version-check -q install -r requirements.txt
python main.py
