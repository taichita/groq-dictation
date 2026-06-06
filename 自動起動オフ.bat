@echo off
chcp 65001 >nul
cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
echo 自動起動を解除し、常駐を停止します...
python autostart.py uninstall
pause
