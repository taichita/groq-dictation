#!/bin/bash
# PC起動(ログイン)と同時に音声入力を常駐させる（ボタン不要に）。
cd "$(dirname "$0")" || exit 1
if [ ! -d ".venv" ]; then
  echo "先に『はじめに.command』でセットアップしてください。"
  read -r -p "Enterで閉じます..." _; exit 1
fi
source .venv/bin/activate
clear
echo "自動起動を有効にします..."
python autostart.py install
echo ""
echo "------------------------------------------------------------"
echo " 権限の許可ダイアログを出します。"
echo "   ・アクセシビリティ → リストの『python』をオンに（ホットキー用）"
echo "   ・マイク          → 『許可』（録音用）"
echo "------------------------------------------------------------"
python permissions.py
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent" 2>/dev/null || true
echo ""
echo "→ 設定で python を有効にしたら、反映のため常駐を再起動します。"
read -r -p "   許可し終えたら Enter を押してください..." _
python autostart.py restart
echo ""
echo "✅ 完了。ホットキーで音声入力を試してください。"
read -r -p "Enterで閉じます..." _
