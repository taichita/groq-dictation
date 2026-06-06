#!/bin/bash
# Groq Dictation 起動スクリプト。
# ダブルクリックではなく、ターミナルで  ./run.sh  と打って使う。
# （マイク/アクセシビリティ権限は「ターミナル」に対して付与されている必要がある）

cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
  echo "仮想環境(.venv)が見つかりません。先に setup を実行してください。"
  echo "  python3.13 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

source .venv/bin/activate
exec python app.py
