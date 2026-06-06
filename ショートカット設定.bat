@echo off
chcp 65001 >nul
cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
echo ショートカット（録音開始/停止キー）を設定します...
python -m hotkey_setup
echo 自動起動中の場合は反映のため再起動します...
python autostart.py restart
pause
