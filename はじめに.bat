@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo    Groq Dictation かんたんセットアップ (Windows)
echo ============================================================
echo.

REM --- Python 検出（py ランチャー優先） ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [!] Python が見つかりません。
  echo     これから開くページからインストールしてください。
  echo     インストール時に「Add python.exe to PATH」に必ずチェックを。
  echo     その後もう一度この はじめに.bat を実行してください。
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)
echo Python: %PY%

REM --- 仮想環境 ---
if not exist ".venv\Scripts\python.exe" (
  echo 仮想環境を作成中...
  %PY% -m venv .venv
)
call ".venv\Scripts\activate.bat"

echo 必要な部品をインストール中（初回は数分かかります）...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q
if errorlevel 1 (
  echo [!] インストールに失敗しました。ネット接続を確認して再実行してください。
  pause
  exit /b 1
)
echo 部品の準備ができました。

echo.
echo === Groq APIキーの設定 ===
python -m key_setup

echo.
echo === ショートカットの設定 ===
python -m hotkey_setup

echo.
echo === 自動起動の設定 ===
python autostart.py install

echo.
echo ============================================================
echo  完了しました！ 次回ログインから自動で常駐します。
echo  入力欄で 設定したショートカット を押して音声入力できます。
echo ============================================================
pause
