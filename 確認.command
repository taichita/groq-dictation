#!/bin/bash
# 動作確認。設定→マイク→3秒テスト録音→Groq送信 を順にチェックし、
# 結果を last_check.log にも保存する。
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate
clear
echo "Groq Dictation 動作確認 — 3秒のテスト録音をします。何か話してください。"
echo ""
python check.py 2>&1 | tee last_check.log
echo ""
read -r -p "Enterで閉じます..." _
