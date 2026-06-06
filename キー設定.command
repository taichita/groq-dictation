#!/bin/bash
# Groq APIキーをいつでも設定し直す。
# 初めての人もこれを最初にダブルクリックすればOK。
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate
clear
echo "Groq APIキーの設定をします。入力ダイアログが出ます..."
python -m key_setup
echo ""
read -r -p "Enterで閉じます..." _
