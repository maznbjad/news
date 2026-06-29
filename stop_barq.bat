@echo off
cd /d "%~dp0"
python -c "from core import update_control; update_control(enabled=False)"
echo Monitoring disabled.
pause
