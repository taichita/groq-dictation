@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 先に はじめに.bat を実行してください。
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
echo Groq Dictation を起動します（ショートカットで録音 / Ctrl+C で終了）。
python app.py
pause
