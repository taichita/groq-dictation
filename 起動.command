#!/bin/bash
# Groq Dictation 起動（ダブルクリック または open -a Terminal で実行）。
# このファイルを実行した「ターミラル.app」に対してマイク/アクセシビリティ権限が付く。
cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
  echo "仮想環境(.venv)が見つかりません。"
  echo "セットアップが必要です。Claudeに伝えてください。"
  read -r -p "Enterで閉じます..." _
  exit 1
fi

source .venv/bin/activate
echo "============================================"
echo " Groq Dictation を起動します"
echo " ・録音/停止: Ctrl + Shift + Space"
echo " ・終了:      Ctrl + C"
echo "============================================"
python app.py
echo ""
read -r -p "終了しました。Enterで閉じます..." _
