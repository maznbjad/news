@echo off
title BARQ NEWS
cd /d "%~dp0"
python -m pip install -r requirements.txt
start "BARQ MONITOR" /MIN python monitor_worker.py
python -m streamlit run app.py
pause
