#!/bin/bash
# マイク・アクセシビリティの許可ダイアログを出し、設定画面を開く。
# 「ホットキーが効かない」「貼り付かない」ときはこれを実行。
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate 2>/dev/null
clear
echo "権限（マイク／アクセシビリティ）の許可を行います..."
echo ""
python permissions.py
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent" 2>/dev/null || true
echo ""
echo "→ リストの『python』をオンにしてください。"
echo "   自動起動中なら、反映のため常駐を再起動します。"
read -r -p "   許可し終えたら Enter..." _
python autostart.py restart 2>/dev/null || true
echo "✅ 完了"
read -r -p "Enterで閉じます..." _
